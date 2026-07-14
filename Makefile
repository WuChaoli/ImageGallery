.PHONY: lint test check

# 自动检测 venv Python，回退到系统 python
ifeq ($(OS),Windows_NT)
    VENV_PY := .venv/Scripts/python.exe
else
    VENV_PY := .venv/bin/python
endif
PYTHON ?= $(if $(wildcard $(VENV_PY)),$(VENV_PY),python)

# 静态检查统一入口：ruff (代码风格 + docstring) + pyright (类型检查)
# pyright 的 warning 不阻断，只有 error 会导致非零退出码
lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m pyright src/image_gallery

# 测试
test:
	$(PYTHON) -m pytest -q

# 一键检查 + 测试
check: lint test
