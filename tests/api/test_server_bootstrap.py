"""启动 bootstrap 不应被 GitHub skill 下载阻塞。"""

from __future__ import annotations

import inspect


def test_bootstrap_core_does_not_sync_download_bundled_skills():
    import friday.server as server_mod

    source = inspect.getsource(server_mod._lifespan)
    bootstrap_block = source.split("def _bootstrap()")[1].split("await asyncio.to_thread(_bootstrap)")[0]
    assert "ensure_bundled_skill_assets()" not in bootstrap_block


def test_lifespan_schedules_bundled_skill_warmup():
    import friday.server as server_mod

    source = inspect.getsource(server_mod._lifespan)
    assert "_bundled_skill_warmup" in source
    assert "asyncio.create_task(_bundled_skill_warmup())" in source
