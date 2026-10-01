# CyberProject

Role-based Cybersecurity Risk Prediction and Awareness System for the final year project. The Flask application validates 63 organization and employee assessment fields, predicts a Low, Medium, or High risk level, reports class probabilities, and selects recommendations from transparent rules.

## Features

- Predicts `Low`, `Medium`, or `High` role-based cybersecurity risk
- Uses preprocessing and classification from one saved model package
- Reports prediction confidence and all class probabilities
- Selects recommendations from the dataset's rule table
- Includes research, FAQ, awareness, contact, and insights pages
- Lets users download a simple report after generating a prediction

## Run The Project

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.

## Share It Online

The easiest way to share the frontend with another group member is to deploy it on Render and send them the public link.

### Fastest Option: Vercel

This project is also prepared for Vercel.

1. Go to Vercel and import `Malshikafernando/CyberProject`.
2. Keep the default detected settings.
3. Deploy the project.

Notes:

- Vercel will use the Flask app from `app.py`.
- Static files are served from the `public/` folder.
- Python version is pinned with `.python-version`.

### Option 1: Render

1. Upload this project to a GitHub repository.
2. Go to Render and create a new `Web Service`.
3. Connect your GitHub repository.
4. Render can use the included `render.yaml` file automatically, or use these values manually:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

5. Add these environment variables if Render does not create them automatically:

```text
SECRET_KEY=<any long random string>
PYTHON_VERSION=3.13.13
```

6. Deploy the service and open the generated public URL.

### Option 2: Quick Local Demo

If you only need a temporary public link for a demo or screen recording, you can also run the project locally and expose it with a tunneling tool such as `ngrok` or `cloudflared`.

## Deployment Notes

- The Flask app now reads `PORT` and `SECRET_KEY` from environment variables for cloud deployment.
- Local development still works with `python app.py`.
- `Procfile` and `render.yaml` are included to make hosted deployment easier.

## Run Tests

```bash
pytest
```

## Important Notes

- The application expects `role_based_cybersecurity_risk_model.pkl` inside the `CyberProject` folder.
- The model package contains preprocessing, classifier, input schema, evaluation metadata, and recommendation rules.
- The folders like `flask-template` and `flask-template-1` are older template copies and are not required for the main app.
- Rebuild the model from the Excel dataset with `.\.venv\Scripts\python.exe scripts\train_model.py`.
- Training uses organization-separated cross-validation and an unseen-organization holdout to prevent organization leakage.
