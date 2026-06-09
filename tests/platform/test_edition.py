from __future__ import annotations

from friday.edition import (
    appdata_folder_name,
    default_workspace_name,
    openclaw_gateway_port,
    window_title,
)
from friday.paths import get_appdata_dir


def test_edition_constants():
    assert window_title() == "星期五"
    assert appdata_folder_name() == "Friday"
    assert default_workspace_name() == "星期五"
    assert openclaw_gateway_port() == 18789
    path = get_appdata_dir()
    assert path.name == "Friday"
