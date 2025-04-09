#!/usr/bin/env python3
"""
Runner script for the J.A.R.V.I.S. AI Assistant.
Run this file to start the application.
"""

import streamlit.web.cli as stcli
import sys
import os

if __name__ == "__main__":
    # Get the directory of this script
    dir_path = os.path.dirname(os.path.realpath(__file__))
    
    # Path to app.py
    app_path = os.path.join(dir_path, "app.py")
    
    # Configure sys.argv for streamlit run
    sys.argv = ["streamlit", "run", app_path, "--server.port=8501", "--server.address=0.0.0.0"]
    
    # Run the app
    sys.exit(stcli.main()) 