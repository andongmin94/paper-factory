//! Reads a compiled PDF and rasterizes single pages for the preview pane.

use std::{path::Path, sync::Arc};

use anyhow::{Context as _, Result, anyhow};
use gpui::RenderImage;
use hayro::{
    PixmapSettings, RenderCache, RenderSettings, hayro_interpret::InterpreterSettings,
    hayro_syntax::Pdf, render, vello_cpu::color::palette::css::WHITE,
};
use image::{Frame, RgbaImage};

/// Pixels rendered per PDF point, so pages stay sharp on high-DPI displays.
const RASTER_SCALE: f32 = 2.0;

/// A loaded PDF. Pages are rendered on demand, so a long manuscript does not
/// hold every page image in memory at once.
pub struct PdfDocument {
    data: Arc<Vec<u8>>,
    /// Each page's size in PDF points.
    pub page_sizes: Vec<(f32, f32)>,
}

impl PdfDocument {
    /// Reads the PDF at `path` and measures its pages.
    pub fn open(path: &Path) -> Result<Self> {
        let data = Arc::new(
            std::fs::read(path)
                .with_context(|| format!("{}을(를) 읽지 못했습니다", path.display()))?,
        );
        let pdf = parse(&data)?;
        let page_sizes = pdf
            .pages()
            .iter()
            .map(|page| page.render_dimensions())
            .collect();
        Ok(Self { data, page_sizes })
    }

    /// Rasterizes one page. Runs on a background thread.
    pub fn render_page(&self, index: usize) -> Result<Arc<RenderImage>> {
        // Parsing shares the bytes and only reads the cross-reference table.
        let pdf = parse(&self.data)?;
        let page = pdf
            .pages()
            .get(index)
            .with_context(|| format!("{}쪽이 없습니다", index + 1))?;
        let pixmap = render(
            page,
            &RenderCache::new(),
            &InterpreterSettings::default(),
            &RenderSettings::default(),
            &PixmapSettings {
                x_scale: RASTER_SCALE,
                y_scale: RASTER_SCALE,
                bg_color: WHITE,
            },
        );
        // Pages are painted on an opaque white background, so premultiplied
        // RGBA equals straight RGBA. GPUI expects BGRA.
        let mut pixels = pixmap.data_as_u8_slice().to_vec();
        for pixel in pixels.as_chunks_mut::<4>().0 {
            pixel.swap(0, 2);
        }
        let buffer = RgbaImage::from_raw(pixmap.width().into(), pixmap.height().into(), pixels)
            .context("페이지 이미지 크기가 맞지 않습니다")?;
        Ok(Arc::new(RenderImage::new(vec![Frame::new(buffer)])))
    }
}

fn parse(data: &Arc<Vec<u8>>) -> Result<Pdf> {
    Pdf::new(data.clone()).map_err(|error| anyhow!("PDF를 해석하지 못했습니다: {error:?}"))
}
