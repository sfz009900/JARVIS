# J.A.R.V.I.S. AI Assistant

A modular Streamlit-based UI for the J.A.R.V.I.S. AI Assistant.

## 🚀 Features

- 💬 Chat interface with AI assistant
- 📸 Image upload (file, camera, clipboard)
- 📱 Responsive design for mobile and desktop
- 🔄 Session management
- 📜 Chat history browsing
- 🎨 Light/dark theme support
- 📊 Device-specific optimizations

## 📋 Project Structure

```
jarvis_ui/
├── app.py                # Main application entry point
├── config.py             # Configuration and constants
├── api/
│   ├── __init__.py
│   └── client.py         # API communication functions
├── components/
│   ├── __init__.py
│   ├── sidebar.py        # Sidebar UI components
│   ├── chat.py           # Chat UI components
│   ├── history.py        # Chat history components
│   └── image_handler.py  # Image upload and display
├── utils/
│   ├── __init__.py
│   ├── state.py          # Session state management
│   ├── device.py         # Device detection utilities
│   └── image_utils.py    # Image processing utilities
└── static/
    └── styles.css        # CSS styles
```

## 🛠️ Setup

1. Install dependencies:

```bash
pip install streamlit pillow requests
```

2. Set up the backend API server (see separate repository).

3. Run the application:

```bash
streamlit run app.py
```

Or alternatively:

```bash
python -m streamlit run app.py
```

## ⚙️ Configuration

Edit `jarvis_ui/config.py` to configure:

- API URL
- Page title and icon
- UI settings
- Avatar URLs
- Version information

## 📱 Device Support

The application is optimized for both desktop and mobile devices with:

- Responsive layout
- Mobile-friendly image upload
- Touch-optimized interactions
- Device-specific UI adjustments

## 📝 Notes

- The backend API server must be running at the configured URL
- For clipboard paste functionality, use desktop browsers
- Camera functionality works best on mobile devices

## 📄 License

MIT License 