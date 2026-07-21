"""Small QR dialogs used by the stock openpilot settings integrations."""

from __future__ import annotations

import numpy as np
import pyray as rl
import qrcode

from openpilot.common.swaglog import cloudlog
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.label import UnifiedLabel
from openpilot.system.ui.widgets.nav_widget import NavWidget


def _qr_texture(url: str, *, light: bool) -> rl.Texture | None:
  try:
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4 if light else 0)
    qr.add_data(url)
    qr.make(fit=True)
    foreground, background = ("black", "white") if light else ("white", "black")
    image = qr.make_image(fill_color=foreground, back_color=background).convert("RGBA")
    pixels = np.array(image, dtype=np.uint8)
    rl_image = rl.Image()
    rl_image.data = rl.ffi.cast("void *", pixels.ctypes.data)
    rl_image.width = image.width
    rl_image.height = image.height
    rl_image.mipmaps = 1
    rl_image.format = rl.PixelFormat.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8
    return rl.load_texture_from_image(rl_image)
  except Exception:
    cloudlog.exception("EV Vehicle Telemetry QR generation failed")
    return None


class TelemetryQRDialog(Widget):
  """Full-size comma 3/3X QR dialog."""

  def __init__(self, url: str, display_url: str):
    super().__init__()
    self._display_url = display_url
    self._texture = _qr_texture(url, light=True)

  def _handle_mouse_release(self, _):
    gui_app.pop_widget()

  @staticmethod
  def _draw_centered(rect: rl.Rectangle, text: str, y: float, size: int, color: rl.Color, weight=FontWeight.NORMAL):
    font = gui_app.font(weight)
    width = measure_text_cached(font, text, size).x
    rl.draw_text_ex(font, text, rl.Vector2(rect.x + (rect.width - width) / 2, y), size, 0, color)

  def _render(self, rect: rl.Rectangle):
    rl.clear_background(rl.Color(238, 238, 238, 255))
    self._draw_centered(rect, "EV Vehicle Telemetry", rect.y + 70, 68, rl.BLACK, FontWeight.BOLD)
    self._draw_centered(rect, "Scan with your phone on the same Wi-Fi", rect.y + 155, 38, rl.Color(70, 70, 70, 255))
    if self._texture is None:
      self._draw_centered(rect, "QR Code Error", rect.y + rect.height / 2, 45, rl.RED, FontWeight.BOLD)
      return
    size = min(rect.height * 0.58, rect.width * 0.42)
    x = rect.x + (rect.width - size) / 2
    y = rect.y + 225
    source = rl.Rectangle(0, 0, self._texture.width, self._texture.height)
    rl.draw_texture_pro(self._texture, source, rl.Rectangle(x, y, size, size), rl.Vector2(0, 0), 0, rl.WHITE)
    self._draw_centered(rect, self._display_url, y + size + 35, 32, rl.Color(70, 70, 70, 255))
    self._draw_centered(rect, "Tap anywhere to close", rect.y + rect.height - 90, 30, rl.Color(100, 100, 100, 255))

  def __del__(self):
    if self._texture and self._texture.id != 0:
      rl.unload_texture(self._texture)


class TelemetryQRDialogMici(NavWidget):
  """Compact comma 4 QR dialog."""

  def __init__(self, url: str):
    super().__init__()
    self._texture = _qr_texture(url, light=False)
    self._title = UnifiedLabel("set up EV telemetry", font_size=48, font_weight=FontWeight.BOLD, line_height=0.8)

  def _render(self, rect: rl.Rectangle):
    if self._texture is None:
      rl.draw_text_ex(gui_app.font(FontWeight.BOLD), "QR Code Error", rl.Vector2(rect.x + 20, rect.y + rect.height / 2 - 15), 30, 0, rl.RED)
      return
    scale = rect.height / self._texture.height
    rl.draw_texture_ex(self._texture, rl.Vector2(round(rect.x + 8), round(rect.y)), 0.0, scale, rl.WHITE)
    label_x = rect.x + 8 + rect.height + 24
    self._title.set_max_width(int(rect.width - label_x))
    self._title.set_position(label_x, rect.y + 16)
    self._title.render()

  def __del__(self):
    if self._texture and self._texture.id != 0:
      rl.unload_texture(self._texture)
