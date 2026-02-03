.PHONY: dashboard notebook present stop

dashboard:
	streamlit run app.py

notebook:
	jupyter notebook notebooks/inventory_analysis.ipynb

present:
	streamlit run app.py --server.headless true & jupyter notebook notebooks/inventory_analysis.ipynb

stop:
	@pkill -f "streamlit run app.py" 2>/dev/null || true
	@pkill -f "jupyter.*inventory_analysis" 2>/dev/null || true
	@echo "Stopped dashboard and notebook"
