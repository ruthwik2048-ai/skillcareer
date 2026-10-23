# SkillCareer

SkillCareer is a Django-based student skill matching web application. Visitors can request to join, and administrators approve requests before student profiles are added. Administrators also create learning batches through Django admin.

## Overview

This project is designed for a simple local learning environment where students can:

- request to join the community, pending administrator approval
- list skills they can teach
- list skills they want to learn
- find peers who can teach or learn from them
- administrator-managed learning batches

## Features

- Admin-approved student profiles
- Student listing page
- Unique student roll numbers and profile updates
- Student profile deletion with a confirmation step
- Career-role suggestions based on students' teachable skills
- Two-way skill matching logic
- Admin-created learning batches with manually selected members
- Staff-authorized learning batch editing
- Admin-managed job listings and skill-based job recommendations
- Private student job dashboards, applications, resume uploads, and application statuses
- SQLite database storage for local development
- Django admin support

## Tech Stack

- Python 3
- Django 5
- SQLite
- HTML templates and Django forms

## Project Structure

```text
skillswap_web/
├── README.md
├── manage.py
├── requirements.txt
├── db.sqlite3
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── matching/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── models.py
│   ├── services.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── migrations/
├── templates/
│   └── matching/
└── run_skillswap.bat
```

## Setup Instructions

### Prerequisites

- Python 3 installed on your system
- Windows environment for the provided launcher script

### Option 1: Run with the launcher

Double-click:

```text
run_skillswap.bat
```

This script will:

1. create a virtual environment if needed
2. install project dependencies
3. apply migrations
4. start the Django server
5. open the app in the browser

### Option 2: Manual setup

Open PowerShell in the project folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then open the app in your browser:

```text
http://127.0.0.1:8000/
```

## Job application confirmation email

After a student successfully applies for a job, SkillCareer sends a confirmation email to the address on their student profile. In local development (`DEBUG=True`), Django prints emails to the server console by default. To deliver real email, configure the SMTP environment variables before starting the server. For Gmail, use an app password rather than your account password:

```powershell
$env:EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST = "smtp.gmail.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_USE_TLS = "True"
$env:EMAIL_HOST_USER = "theskillcareer.hub@gmail.com"
$env:EMAIL_HOST_PASSWORD = "<your Gmail app password>"
$env:DEFAULT_FROM_EMAIL = "SkillCareer <theskillcareer.hub@gmail.com>"
python manage.py runserver
```

Keep the app password private and do not commit it to source control. For deployment, set these variables in the hosting provider's environment configuration. If email delivery fails, the application remains submitted and the student sees a warning on the dashboard.

## Application Output

When the Django server starts successfully, you should see output similar to:

```text
Watching for file changes with StatReloader
```

The browser will display the home page with a title like:

```text
Students · SkillCareer
```

This means the project is running correctly.

## How the App Works

1. Submit a request to join the community with your name, email, and skills.
2. An administrator reviews the request in Django admin and approves it to create your student profile.
3. Browse student profiles and open a profile to view its skill matches.
4. The system evaluates which students can teach skills the selected student wants to learn.
5. It also checks which students want skills that the selected student can teach.
6. An administrator can create learning batches through Django admin, select the admin creator, and choose the students to include.
7. Batches can be viewed from the Batches section.
8. When an administrator approves a registration request or adds a student in Django admin, the app creates and links a student login automatically. The roll number is the username, and the administrator can view the student's six-digit login code in the separate **Student login codes** admin section. Codes are stored in the database to make them available there; protect database backups and restrict admin access accordingly.
9. An administrator adds job listings in Django admin. Students sign in at `/student/login/`, browse jobs, apply with a PDF resume (up to 5 MB) and optional cover note, receive an application confirmation email, and track application statuses at `/student/dashboard/`.
10. Job postings receive an application deadline one calendar month after creation by default. Expired jobs stop accepting applications. A daily run of `python manage.py renew_expired_jobs` creates one new copy of each expired active job, with a fresh one-month deadline. The copy is created only once per original job.

Phone numbers are not collected, and there is no OTP sign-in flow. Visitors can browse student profiles, matches, and batches without signing in. Registration requests require administrator approval; resolved requests leave the default pending queue but remain available in the admin status filters for history. Only administrators create student profiles and learning batches through Django admin.

Existing student passwords remain unchanged when this feature is installed because they cannot be recovered from their password hashes. Such students appear as **Not generated** in **Student login codes** until an administrator selects them and runs **Generate/reset six-digit codes for selected students**; this creates and stores a new code and updates their login password.

Job resumes are stored under `private_uploads/` and are not served as public media. Resume downloads require the owning student to be signed in or a staff account. Back up the private upload directory securely alongside the database.

### Schedule job renewals on Windows

Run `python manage.py renew_expired_jobs` once per day using Windows Task Scheduler so expired jobs are renewed automatically:

1. Open **Task Scheduler** and choose **Create Basic Task**.
2. Name it `SkillCareer job renewals` and set the trigger to **Daily**.
3. For the action, choose **Start a program**.
4. Set **Program/script** to the project's Python executable, for example `C:\path\to\skillswap_web\.venv\Scripts\python.exe`.
5. Set **Add arguments** to `manage.py renew_expired_jobs`.
6. Set **Start in** to the project directory, for example `C:\path\to\skillswap_web`.
7. Finish and use **Run** once to test it. The command reports how many jobs it renewed.

The scheduled task must use the same project directory and Python environment as the website so it updates the same database. It can run while the development server is stopped.

## Public deployment on PythonAnywhere

The Windows launcher runs a local development server only while its console is open. For a site that remains available independently of your computer, deploy it to a hosting service. The following steps prepare a PythonAnywhere manual web app; you will need a PythonAnywhere account and your account's deployment credentials.

1. Upload or clone this project into your PythonAnywhere home directory, for example `/home/yourusername/skillswap_web`.
2. In a PythonAnywhere Bash console, create a virtual environment and install the app:

   ```bash
   cd ~/skillswap_web
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python manage.py migrate
   .venv/bin/python manage.py collectstatic --noinput
   ```

3. In the PythonAnywhere **Web** tab, create a manual-config web app using the same Python version as the virtual environment. Set its virtualenv path to `/home/yourusername/skillswap_web/.venv`.
4. Edit the web app's WSGI configuration file. Replace `yourusername` with your PythonAnywhere username and set a long, private secret value in the hosting configuration (do not commit it):

   ```python
   import os
   import sys

   project_home = "/home/yourusername/skillswap_web"
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
   os.environ["DJANGO_DEBUG"] = "False"
   os.environ["DJANGO_SECRET_KEY"] = "replace-with-a-long-private-random-value"
   os.environ["ALLOWED_HOSTS"] = "yourusername.pythonanywhere.com"
   from django.core.wsgi import get_wsgi_application

   application = get_wsgi_application()
   ```

5. In the Web tab's **Static files** section, map URL `/static/` to `/home/yourusername/skillswap_web/staticfiles/`.
6. Reload the web app from the Web tab and open `https://yourusername.pythonanywhere.com/`.

The SQLite database is stored in the project directory, so keep that directory persistent and arrange backups. Hosting availability depends on your PythonAnywhere account and plan; no service can guarantee a site will stay online permanently.

## Admin Access

To access Django's admin panel, create a superuser:

```powershell
python manage.py createsuperuser
```

Then open:

```text
http://127.0.0.1:8000/admin/
```


## Database

The project uses SQLite for local development.

- Database file: `db.sqlite3`
- Useful for quick testing and demos without external database setup

## Notes

This app is intended for development and demonstration purposes. Before deployment to production, ensure that:

- the secret key is changed
- debug mode is disabled
- allowed hosts are configured
- a production-ready database is used

## Quick Start Summary

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Then visit:

```text
http://127.0.0.1:8000/
```
