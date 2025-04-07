# CVMaker 🧾

CVMaker is a Django-based web application designed to dynamically generate professional CVs (resumes). It features a clean and customizable UI and supports PDF export for easy sharing.

---

## 🚀 Usage

Follow the steps below to set up and run CVMaker locally:

### 1. Clone the Repository

```bash
git clone https://github.com/NatanSisoev/CVMaker.git
cd CVMaker
```

### 2. Create and Activate a Python Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Django Migrations

```bash
python manage.py migrate
```

### 5. (Optional) Create a Superuser for Admin Access

```bash
python manage.py createsuperuser
```

### 6. Run the Development Server

```bash
python manage.py runserver
```

Then visit [http://localhost:8000](http://localhost:8000) in your browser.
