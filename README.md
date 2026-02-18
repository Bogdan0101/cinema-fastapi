# Project description

FastAPI framework project for managing cinema service  
with users, user profiles, carts, orders, payments, movies, genres,  
stars, directors, reviews, ratings, favorites and certifications.
This project is a backend for Cinema Service, built using Python 3.12 and FastAPI.
Supports PostgreSQL database and can be fully deployed using Docker.  
Additionally, it can send messages via Email (aiosmtplib) and handle payments through Stripe sessions.

# Features

1. JWT Authentication: Secure access with Activation, Password Reset, and Refresh Tokens.
2. User Profiles: Separate management of auth data and personal user information.
3. Permissions & Roles:
    - **Admin**: Full system access. Can **create moderators**, manage user statuses (**ban/unban users**), and oversee
      all system entities;
    - **Moderator**: Authorized to manage the movie catalog (stars, directors, genres) and moderate user reviews;
    - **User**: Can manage their own profile, favorites, write reviews, and process orders/payments;
    - **Unauthenticated**: Limited to browsing the movie catalog and accessing registration/login endpoints.
4. E-commerce Workflow: Integrated shopping Carts, Orders, and Stripe payment processing:  
   - Supports multiple order statuses: `PENDING`, `PAID`, and `CANCELED`;  
   - Tracks payment history with statuses: `SUCCESSFUL`, `CANCELED`, and `REFUNDED`.  
5. Automated Tasks: `APScheduler` integration for cleaning up expired tokens and system maintenance.
6. Email System: Asynchronous email notifications using `Jinja2` templates and aiosmtplib.
7. CI/CD: Automated testing and linting workflow via GitHub Actions.
8. Reliability: 49 tests with 79% code coverage.

# Technologies used

1. Python 3.12
2. FastAPI & Uvicorn
3. SQLAlchemy 2.0 (Async) & Alembic
4. PostgreSQL 18 (asyncpg)
5. Poetry (Dependency Management)
6. Docker & Docker Compose
7. Stripe API
8. Pytest & Pytest-cov
9. APScheduler
10. GitHub Actions

# DB structure

<img width="1953" height="1061" alt="Untitled" src="https://github.com/user-attachments/assets/fdd42708-43d9-4e78-9d26-c1ff14e2038b" />

# User admin:

Email: admin@example.com  
Password: Adminpass1!

# PyCharm Configuration (Optional)

If you are using PyCharm, for better development experience:

- Right-click on the **src** folder -> Mark Directory as -> Sources Root.
- Right-click on your **templates** folder -> Mark Directory as -> Template Folder.

# Installation instructions GitHub

1. git clone https://github.com/Bogdan0101/cinema-fastapi.git
2. cd cinema-fastapi
3. poetry install
4. Create a **.env** file using the example **.env.sample**
5. poetry run alembic upgrade head
6. poetry run uvicorn src.main:app --reload
7. Open in browser http://127.0.0.1:8000/docs

# Docker Deployment

8. docker-compose up --build
9. Open in browser http://localhost:8000/docs

# Quality Assurance

To run tests with coverage report:

10. poetry run pytest --cov=src

# Screenshots  

<img width="1552" height="952" alt="image" src="https://github.com/user-attachments/assets/b59ff746-53fb-4074-9652-927d9cdc5de5" />

<img width="1551" height="955" alt="image" src="https://github.com/user-attachments/assets/a177b653-17f9-42bf-b488-a84422de4160" />

<img width="1570" height="959" alt="image" src="https://github.com/user-attachments/assets/3fb37e86-377d-4529-b8c6-eede74a683e9" />

<img width="1529" height="944" alt="image" src="https://github.com/user-attachments/assets/71b47d97-f37b-43b1-80ab-18d0fddb6ee2" />

<img width="1565" height="957" alt="image" src="https://github.com/user-attachments/assets/986962a8-c11c-4c41-b8c8-d9ff8b6f1b4c" />

<img width="1557" height="963" alt="image" src="https://github.com/user-attachments/assets/dc038f4f-ad4a-427f-b850-027ee4948a86" />

<img width="1913" height="960" alt="image" src="https://github.com/user-attachments/assets/4c186f1c-fb62-487d-b687-8c652b66c3f2" />

<img width="1384" height="149" alt="image" src="https://github.com/user-attachments/assets/58dc941c-7341-40ed-b488-183a1571b5c2" />

<img width="1332" height="547" alt="image" src="https://github.com/user-attachments/assets/328d5e96-9854-4fa7-97b7-e0f3e8bf3d24" />

<img width="1360" height="565" alt="image" src="https://github.com/user-attachments/assets/67f5dbe6-7397-4419-b923-775aec3c5790" />

<img width="1309" height="445" alt="image" src="https://github.com/user-attachments/assets/215cb233-56c3-4ef0-a796-7474361493c7" />
