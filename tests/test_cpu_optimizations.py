import importlib
import sys


def _reload_module(monkeypatch, module_name: str):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test_cpu_optimizations.sqlite")
    monkeypatch.setenv("LOW_CPU_MODE", "true")
    for name in [
        module_name,
        "app.core.config",
        "app.db.session",
        "app.core.env_loader",
    ]:
        sys.modules.pop(name, None)
    return importlib.import_module(module_name)


def test_message_scraper_prefilters_low_signal_messages(monkeypatch):
    module = _reload_module(monkeypatch, "app.services.message_scraper")
    scraper = module.MessageScraper()

    assert scraper._should_run_deep_analysis("hello everyone") is False
    assert scraper._should_run_deep_analysis("any good iptv provider?") is True
    assert scraper._contains_possible_invite_link("join here https://t.me/example") is True


def test_memory_engine_deduplicates_summary_scheduling(monkeypatch):
    module = _reload_module(monkeypatch, "app.services.memory_engine")
    engine = module.ConversationMemoryEngine()
    scheduled = []

    def _fake_create_task(coro):
        scheduled.append("task")
        coro.close()
        return "task"

    monkeypatch.setattr(module.asyncio, "create_task", _fake_create_task)

    engine.schedule_conversation_summary("user-1")
    engine.schedule_conversation_summary("user-1")
    engine.schedule_conversation_summary("user-2")

    assert len(scheduled) == 2
