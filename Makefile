PYTHON = python

.PHONY: load ratios test report dashboard api clean

load:
    $(PYTHON) -m db.loader

ratios:
    $(PYTHON) -m src.analytics.populate_ratios

test:
    $(PYTHON) -m pytest tests -v

report:
    $(PYTHON) -c "from pathlib import Path; print('Report module ready' if Path('src/reports/portfolio_report.py').exists() else 'Report module scheduled for later sprint')"

dashboard:
    $(PYTHON) -c "from pathlib import Path; print('Dashboard module ready' if Path('src/dashboard/app.py').exists() else 'Dashboard module scheduled for Sprint 4')"

api:
    $(PYTHON) -c "from pathlib import Path; print('API module ready' if Path('src/api/main.py').exists() else 'API module scheduled for Sprint 6')"

clean:
    $(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc') if p.exists()]; print('Python cache files removed')"
