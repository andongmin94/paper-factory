use super::{Icon, Preset, Tokens};
use gpui::{prelude::*, *};
use gpui_deck::{
    Chart, ChartSeries, ChartState, InputAccessibility, InputState, input::InputEvent,
};

const MONTHS: [&str; 6] = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov"];
const PUBLISHED: [f64; 6] = [6., 9., 7., 13., 10., 15.];
const IN_REVIEW: [f64; 6] = [3., 5., 4., 6., 5., 8.];

pub struct Showcase {
    tokens: Tokens,
    chart: Entity<ChartState>,
    name: Entity<InputState>,
    reports: Vec<SharedString>,
}

impl Showcase {
    pub fn new(preset: Preset, dark: bool, window: &mut Window, cx: &mut Context<Self>) -> Self {
        let tokens = preset.tokens(dark);
        let chart = cx.new(|cx| {
            ChartState::new(
                MONTHS,
                [
                    ChartSeries::new("Published", PUBLISHED),
                    ChartSeries::new("In review", IN_REVIEW),
                ],
                cx,
            )
        });
        cx.observe(&chart, |_, _, cx| cx.notify()).detach();
        let name = cx.new(|cx| {
            let mut state = InputState::new(window, cx).placeholder("November activity");
            state.set_accessibility(
                InputAccessibility::new(Some(Role::TextInput))
                    .with_label(Some("Report name".into())),
            );
            state.set_editor_style(tokens.editor_style());
            state
        });
        cx.subscribe_in(&name, window, |this: &mut Self, _, event, window, cx| {
            if matches!(
                event,
                InputEvent::PressEnter {
                    secondary: false,
                    shift: false
                }
            ) {
                this.save(window, cx);
            } else {
                cx.notify();
            }
        })
        .detach();
        Self {
            tokens,
            chart,
            name,
            reports: vec!["October activity".into()],
        }
    }

    /// Update styles in place, keeping the draft, saved reports and chart focus.
    pub fn set_preset(&mut self, preset: Preset, dark: bool, cx: &mut Context<Self>) {
        self.tokens = preset.tokens(dark);
        self.name.update(cx, |state, _| {
            state.set_editor_style(self.tokens.editor_style())
        });
        cx.notify();
    }

    fn save(&mut self, window: &mut Window, cx: &mut Context<Self>) {
        let value = self.name.read(cx).value();
        let trimmed = value.trim();
        if !trimmed.is_empty() {
            self.reports.push(trimmed.to_owned().into());
            self.name
                .update(cx, |state, cx| state.set_value("", window, cx));
            cx.notify();
        }
    }

    fn heading(&self, text: &'static str) -> Div {
        div()
            .font_family(self.tokens.heading)
            .font_weight(FontWeight::SEMIBOLD)
            .text_size(px(21.))
            .child(text)
    }

    fn chart_card(&self, window: &Window, cx: &App) -> Div {
        let t = self.tokens;
        let state = self.chart.read(cx);
        let selected = state.inspected_index();
        let readout = state.inspected_description_with(|value| format!("{value:.0}"));
        let plot = Chart::new(
            "release-activity-plot",
            &self.chart,
            "Monthly release counts",
        )
        .value_description(readout.clone())
        .w_full()
        .h(px(136.))
        .flex()
        .items_end()
        .border_b_1()
        .border_color(if state.focus_handle().is_focused(window) {
            t.accent
        } else {
            t.border
        })
        .children(MONTHS.iter().enumerate().map(|(i, _)| {
            let bars = [PUBLISHED[i], IN_REVIEW[i]]
                .into_iter()
                .zip(t.chart)
                .map(|(n, color)| {
                    div()
                        .w(px(13.))
                        .max_w(relative(0.36))
                        .h(px((n * 8.) as f32))
                        .rounded_t(t.radius.min(px(4.)))
                        .bg(color)
                });
            div()
                .flex_1()
                .h_full()
                .min_w_0()
                .flex()
                .items_end()
                .justify_center()
                .gap(px(2.))
                .when(selected == Some(i), |v| v.bg(t.accent.opacity(0.055)))
                .children(bars)
        }));
        let labels = div()
            .w_full()
            .flex()
            .text_size(px(11.))
            .text_color(t.muted)
            .children(MONTHS.map(|month| div().flex_1().min_w_0().text_center().child(month)));
        let legend = div().flex().flex_wrap().gap_3().children(
            ["Published", "In review"]
                .into_iter()
                .zip(t.chart)
                .map(|(label, color)| {
                    div()
                        .flex()
                        .items_center()
                        .gap_1()
                        .text_size(px(12.))
                        .text_color(t.muted)
                        .child(div().size(px(8.)).rounded_full().bg(color))
                        .child(label)
                }),
        );
        t.panel()
            .flex_1()
            .min_w_0()
            .p_5()
            .flex()
            .flex_col()
            .gap_3()
            .child(
                div()
                    .flex()
                    .items_center()
                    .justify_between()
                    .gap_2()
                    .child(self.heading("Release activity"))
                    .child(t.icons.icon(Icon::Activity, 22., t.accent)),
            )
            .child(
                div()
                    .text_color(t.muted)
                    .text_size(px(13.))
                    .child("Last six months"),
            )
            .child(
                div()
                    .flex()
                    .flex_wrap()
                    .items_baseline()
                    .gap_2()
                    .child(
                        div()
                            .font_family(t.heading)
                            .text_size(px(38.))
                            .font_weight(FontWeight::SEMIBOLD)
                            .child(format!("{:.0}", PUBLISHED.iter().sum::<f64>())),
                    )
                    .child(div().text_color(t.muted).child("published releases")),
            )
            .child(legend)
            .child(plot)
            .child(labels)
            .child(div().text_size(px(12.)).text_color(t.muted).child(readout))
    }

    fn reports_card(&self, window: &Window, cx: &mut Context<Self>) -> Div {
        let t = self.tokens;
        let list = div()
            .flex()
            .flex_col()
            .children(self.reports.iter().rev().map(|name| {
                div()
                    .py_2()
                    .border_t_1()
                    .border_color(t.border)
                    .flex()
                    .items_center()
                    .gap_2()
                    .child(t.icons.icon(Icon::Bookmark, 15., t.muted))
                    .child(div().min_w_0().flex_1().truncate().child(name.clone()))
            }));
        t.panel()
            .flex_1()
            .min_w_0()
            .p_5()
            .flex()
            .flex_col()
            .gap_4()
            .child(
                div()
                    .flex()
                    .items_center()
                    .justify_between()
                    .gap_2()
                    .child(self.heading("Saved reports"))
                    .child(t.icons.icon(Icon::Bookmark, 22., t.accent)),
            )
            .child(t.field("report-name", "Report name", &self.name, window, cx))
            .child(
                t.button("save-report", "Save report")
                    .disabled(self.name.read(cx).value().trim().is_empty())
                    .on_click(cx.listener(|this, _, window, cx| this.save(window, cx))),
            )
            .child(list)
    }
}

impl Render for Showcase {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let t = self.tokens;
        let narrow = window.viewport_size().width < px(640.);
        let cards = div()
            .flex()
            .gap_4()
            .items_start()
            .when(narrow, |v| v.flex_col().items_stretch())
            .child(self.chart_card(window, cx))
            .child(self.reports_card(window, cx));
        div()
            .id("release-workspace")
            .size_full()
            .overflow_y_scroll()
            .bg(t.canvas)
            .text_color(t.ink)
            .font_family(t.font)
            .text_size(px(14.))
            .child(
                div()
                    .w_full()
                    .min_h_full()
                    .flex()
                    .items_center()
                    .justify_center()
                    .p(px(if narrow { 14. } else { 24. }))
                    .child(div().w_full().max_w(px(960.)).min_w_0().child(cards)),
            )
    }
}
