//! The PDF preview pane: renders only the pages in view, zooms, and keeps the
//! last good PDF on screen while showing compile problems.

use std::{
    collections::{HashMap, HashSet},
    ops::Range,
    sync::Arc,
};

use gpui::{
    AnyElement, Context, EventEmitter, FontWeight, InteractiveElement as _, IntoElement,
    ListHorizontalSizingBehavior, ParentElement as _, Pixels, Render, RenderImage, Role,
    SharedString, StatefulInteractiveElement as _, Styled as _, UniformListScrollHandle, Window,
    canvas, div, img, px, uniform_list,
};
use gpui_deck::Button;

use crate::{
    compile::Problem,
    pdf::PdfDocument,
    ui::{Palette, preset::Tokens, recipes::ButtonVariant},
    workspace::MODIFIER_KEY,
};

/// Rendered pages kept in memory; each is several megabytes.
const MAX_CACHED_PAGES: usize = 10;
/// Space around each page, in pixels.
const PAGE_GAP: f32 = 16.;
const MIN_ZOOM: f32 = 0.25;
const MAX_ZOOM: f32 = 3.0;
const ZOOM_STEP: f32 = 1.2;

#[derive(Clone, Copy, PartialEq)]
enum Zoom {
    FitWidth,
    Scale(f32),
}

/// Requests from the preview to the rest of the window.
pub enum PreviewEvent {
    /// A problem with a known source line was clicked.
    JumpToLine(usize),
}

pub struct PdfPreview {
    document: Option<Arc<PdfDocument>>,
    /// Increases with each new document, so late renders of an old one are dropped.
    generation: u64,
    /// Rendered pages by index, tagged with the generation they belong to.
    /// Older generations stay visible until their replacement arrives.
    pages: HashMap<usize, (u64, Arc<RenderImage>)>,
    pending: HashSet<usize>,
    visible: Range<usize>,
    zoom: Zoom,
    pane_width: Pixels,
    problems: Vec<Problem>,
    message: Option<SharedString>,
    status: Option<SharedString>,
    scroll: UniformListScrollHandle,
    tokens: Tokens,
}

impl EventEmitter<PreviewEvent> for PdfPreview {}

impl PdfPreview {
    pub fn new(tokens: Tokens) -> Self {
        Self {
            document: None,
            generation: 0,
            pages: HashMap::new(),
            pending: HashSet::new(),
            visible: 0..0,
            zoom: Zoom::FitWidth,
            pane_width: px(0.),
            problems: Vec::new(),
            message: Some("컴파일(Ctrl+B)하면 PDF가 여기에 표시됩니다.".into()),
            status: None,
            scroll: UniformListScrollHandle::new(),
            tokens,
        }
    }

    /// Shows a newly compiled or opened PDF and clears earlier problems.
    pub fn set_document(
        &mut self,
        document: Arc<PdfDocument>,
        status: Option<SharedString>,
        cx: &mut Context<Self>,
    ) {
        self.generation += 1;
        self.pending.clear();
        let count = document.page_sizes.len();
        self.pages.retain(|index, _| *index < count);
        self.document = Some(document);
        self.problems.clear();
        self.message = None;
        self.status = status;
        cx.notify();
    }

    /// Shows compile problems above the last good PDF.
    pub fn set_problems(&mut self, problems: Vec<Problem>, cx: &mut Context<Self>) {
        self.problems = problems;
        cx.notify();
    }

    /// Replaces everything with a message, for a manuscript without a PDF.
    pub fn set_message(&mut self, message: impl Into<SharedString>, cx: &mut Context<Self>) {
        self.generation += 1;
        self.document = None;
        self.pages.clear();
        self.pending.clear();
        self.problems.clear();
        self.status = None;
        self.message = Some(message.into());
        cx.notify();
    }

    pub fn zoom_in(&mut self, cx: &mut Context<Self>) {
        self.zoom = Zoom::Scale((self.scale() * ZOOM_STEP).min(MAX_ZOOM));
        cx.notify();
    }

    pub fn zoom_out(&mut self, cx: &mut Context<Self>) {
        self.zoom = Zoom::Scale((self.scale() / ZOOM_STEP).max(MIN_ZOOM));
        cx.notify();
    }

    pub fn zoom_to_fit(&mut self, cx: &mut Context<Self>) {
        self.zoom = Zoom::FitWidth;
        cx.notify();
    }

    /// Pixels per PDF point at the current zoom.
    fn scale(&self) -> f32 {
        match self.zoom {
            Zoom::Scale(scale) => scale,
            Zoom::FitWidth => {
                let widest = self.largest_page().0;
                let available = f32::from(self.pane_width) - 2. * PAGE_GAP;
                if widest <= 0. || available <= 0. {
                    0.9
                } else {
                    (available / widest).clamp(MIN_ZOOM, MAX_ZOOM)
                }
            }
        }
    }

    fn largest_page(&self) -> (f32, f32) {
        self.document.as_ref().map_or((0., 0.), |document| {
            document
                .page_sizes
                .iter()
                .fold((0., 0.), |(w, h), (pw, ph)| (w.max(*pw), h.max(*ph)))
        })
    }

    /// Starts rendering a page unless it is current or already underway.
    fn request(&mut self, index: usize, cx: &mut Context<Self>) {
        let Some(document) = self.document.clone() else {
            return;
        };
        let current = self
            .pages
            .get(&index)
            .is_some_and(|(generation, _)| *generation == self.generation);
        if current || !self.pending.insert(index) {
            return;
        }
        let generation = self.generation;
        cx.spawn(async move |this, cx| {
            let image = cx
                .background_executor()
                .spawn(async move { document.render_page(index) })
                .await;
            this.update(cx, |this, cx| {
                if this.generation != generation {
                    return;
                }
                this.pending.remove(&index);
                if let Ok(image) = image {
                    this.pages.insert(index, (generation, image));
                    this.evict();
                    cx.notify();
                }
            })
            .ok();
        })
        .detach();
    }

    /// Drops the pages farthest from view once the cache is full.
    fn evict(&mut self) {
        while self.pages.len() > MAX_CACHED_PAGES {
            let center = (self.visible.start + self.visible.end) / 2;
            let generation = self.generation;
            let farthest = self
                .pages
                .iter()
                .filter(|(index, _)| !self.visible.contains(index))
                .max_by_key(|(index, (page_generation, _))| {
                    (*page_generation != generation, index.abs_diff(center))
                })
                .map(|(index, _)| *index);
            match farthest {
                Some(index) => self.pages.remove(&index),
                None => break,
            };
        }
    }

    fn render_page(&self, index: usize, scale: f32, slot_width: f32) -> AnyElement {
        let (width, height) = self
            .document
            .as_ref()
            .and_then(|document| document.page_sizes.get(index).copied())
            .unwrap_or_default();
        let item_height = self.largest_page().1 * scale + PAGE_GAP;
        let page = div()
            .w(px(width * scale))
            .h(px(height * scale))
            .flex_none()
            .bg(gpui::white())
            .border_1()
            .border_color(self.tokens.border)
            .shadow_sm();
        let page = match self.pages.get(&index) {
            Some((_, image)) => page.child(img(image.clone()).size_full()),
            None => page
                .flex()
                .items_center()
                .justify_center()
                .text_color(self.tokens.muted)
                .child(format!("{}쪽", index + 1)),
        };
        div()
            .id(("page", index))
            .role(Role::Image)
            .aria_label(format!("{}쪽", index + 1))
            .h(px(item_height))
            .min_w(px(slot_width))
            .w_full()
            .pt(px(PAGE_GAP))
            .flex()
            .justify_center()
            .child(page)
            .into_any_element()
    }

    fn palette(&self) -> Palette {
        Palette {
            control_height: gpui::rems(1.625),
            font_size: gpui::rems(0.8125),
            ..self.tokens.palette()
        }
    }

    fn render_toolbar(&self, cx: &Context<Self>) -> impl IntoElement {
        let tokens = self.tokens;
        let palette = self.palette();
        let percent = format!("{}%", (self.scale() * 100.).round());
        let has_document = self.document.is_some();
        let zoom_button =
            |id: &'static str, label: &'static str, description: String, disabled: bool| {
                ButtonVariant::Ghost
                    .apply(Button::new(id), palette)
                    .accessibility_label(description)
                    .disabled(disabled)
                    .child(label)
            };
        div()
            .h(px(38.))
            .flex_none()
            .flex()
            .items_center()
            .gap_1()
            .px_3()
            .bg(tokens.surface)
            .border_b_1()
            .border_color(tokens.border)
            .text_sm()
            .child(
                div()
                    .mr_2()
                    .text_xs()
                    .font_weight(FontWeight::SEMIBOLD)
                    .text_color(tokens.muted)
                    .child("PDF"),
            )
            .child(
                zoom_button(
                    "zoom-out",
                    "−",
                    format!("축소 ({MODIFIER_KEY}+-)"),
                    !has_document,
                )
                .on_click(cx.listener(|this, _, _, cx| this.zoom_out(cx))),
            )
            .child(
                div()
                    .w(px(44.))
                    .flex()
                    .justify_center()
                    .text_xs()
                    .text_color(tokens.muted)
                    .child(percent),
            )
            .child(
                zoom_button(
                    "zoom-in",
                    "+",
                    format!("확대 ({MODIFIER_KEY}+=)"),
                    !has_document,
                )
                .on_click(cx.listener(|this, _, _, cx| this.zoom_in(cx))),
            )
            .child(
                zoom_button(
                    "zoom-fit",
                    "폭 맞춤",
                    format!("폭에 맞추기 ({MODIFIER_KEY}+0)"),
                    !has_document || self.zoom == Zoom::FitWidth,
                )
                .on_click(cx.listener(|this, _, _, cx| this.zoom_to_fit(cx))),
            )
            .child(
                div()
                    .ml_auto()
                    .text_xs()
                    .text_color(tokens.muted)
                    .truncate()
                    .children(self.status.clone()),
            )
    }

    fn render_problems(&self, cx: &Context<Self>) -> Option<impl IntoElement> {
        if self.problems.is_empty() {
            return None;
        }
        let heading = if self.document.is_some() {
            "컴파일하지 못했습니다. 아래는 마지막으로 성공한 PDF입니다."
        } else {
            "컴파일하지 못했습니다."
        };
        let error = self.palette().error;
        let rows = self.problems.iter().enumerate().map(|(index, problem)| {
            let row = div()
                .font_family(crate::workspace::EDITOR_FONT)
                .text_xs()
                .child(problem.text.clone());
            match problem.line {
                Some(line) => Button::new(("problem", index))
                    .accessibility_label(format!("{}번째 줄로 이동: {}", line + 1, problem.text))
                    .w_full()
                    .px_1()
                    .rounded_sm()
                    .flex()
                    .justify_start()
                    .text_color(self.tokens.ink)
                    .hover(|style| style.bg(error.opacity(0.08)))
                    .on_click(
                        cx.listener(move |_, _, _, cx| cx.emit(PreviewEvent::JumpToLine(line))),
                    )
                    .child(row)
                    .into_any_element(),
                None => div().px_1().child(row).into_any_element(),
            }
        });
        Some(
            div()
                .id("problems")
                .role(Role::Alert)
                .m_2()
                .p_2()
                .max_h(px(180.))
                .overflow_y_scroll()
                .flex()
                .flex_col()
                .gap_1()
                .rounded(self.tokens.radius)
                .border_1()
                .border_color(error.opacity(0.4))
                .bg(error.opacity(0.06))
                .child(
                    div()
                        .text_color(error)
                        .text_sm()
                        .font_weight(FontWeight::MEDIUM)
                        .child(heading),
                )
                .children(rows),
        )
    }
}

impl Render for PdfPreview {
    fn render(&mut self, _: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let entity = cx.entity();
        // Measure the pane so fit-width zoom follows window and layout changes.
        let measure = canvas(
            |bounds, _, _| bounds.size.width,
            move |_, width, _, cx| {
                entity.update(cx, |this, cx| {
                    if (this.pane_width - width).abs() > px(0.5) {
                        this.pane_width = width;
                        cx.notify();
                    }
                })
            },
        )
        .absolute()
        .size_full();

        let body: AnyElement = match &self.document {
            Some(document) => {
                let scale = self.scale();
                let slot_width = self.largest_page().0 * scale + 2. * PAGE_GAP;
                let overflows = slot_width > f32::from(self.pane_width);
                uniform_list(
                    "pages",
                    document.page_sizes.len(),
                    cx.processor(move |this, range: Range<usize>, _, cx| {
                        this.visible = range.clone();
                        range
                            .map(|index| {
                                this.request(index, cx);
                                this.render_page(index, scale, slot_width)
                            })
                            .collect::<Vec<_>>()
                    }),
                )
                .track_scroll(&self.scroll)
                .with_horizontal_sizing_behavior(if overflows {
                    ListHorizontalSizingBehavior::Unconstrained
                } else {
                    ListHorizontalSizingBehavior::FitList
                })
                .flex_1()
                .pb(px(PAGE_GAP))
                .into_any_element()
            }
            None => div()
                .p_6()
                .text_sm()
                .text_color(self.tokens.muted)
                .children(self.message.clone())
                .into_any_element(),
        };

        div()
            .id("preview")
            .role(Role::Region)
            .aria_label("PDF 미리보기")
            .size_full()
            .flex()
            .flex_col()
            .bg(self.tokens.canvas)
            .child(self.render_toolbar(cx))
            .children(self.render_problems(cx))
            .child(
                div()
                    .relative()
                    .flex_1()
                    .min_h_0()
                    .flex()
                    .flex_col()
                    .child(measure)
                    .child(body),
            )
    }
}
