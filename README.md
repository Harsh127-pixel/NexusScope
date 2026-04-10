# NexusScope — OSINT Digital Intelligence Aggregation Platform

NexusScope is a high-performance, modular OSINT (Open Source Intelligence) platform designed for real-time investigation and digital footprint analysis.

## Architecture
- **Frontend**: Vue 3 + Quasar Framework (SPA) - Sleek, responsive investigative dashboard.
- **Backend**: FastAPI (Python) - High-concurrency API layer for coordination.
- **Task Queue**: Celery + Redis - Asynchronous execution of heavy OSINT scanning modules.
- **Database**: Google Firestore - NoSQL storage for flexible intelligence data structures.
- **OSINT Modules**: Modular workers utilizing Playwright, BeautifulSoup, DNSPython, and ExifRead.

## Project Structure
- `/frontend`: Investigative dashboard built with Quasar.
- `/backend`: Core API handling authentication, job submission, and data retrieval.
- `/workers`: Celery workers executing distributed OSINT tasks.
- `/shared`: Shared Pydantic schemas and utility types.

## Tech Stack
- **API**: FastAPI
- **Intelligence Core**: Python (Playwright, BeautifulSoup4, dnspython, exifread)
- **UI/UX**: Quasar Framework (Vue 3, Pinia)
- **Storage**: Firebase Firestore
- **Messaging**: Redis (Broker) + Celery (Workers)

## Getting Started
1. Clone the repo.
2. Setup `.env` based on `.env.example`.
3. Run with Docker Compose: `docker-compose up --build`.

## OSINT Modules Roadmap
- [ ] DNS Intelligence (A, MX, TXT, SPF, DKIM)
- [ ] Web Scraper (Meta tags, Technology stack, SSL info)
- [ ] Image Analysis (Exif Metadata)
- [ ] Social Linkage (Username cross-referencing)
- [ ] Automated Reporting (PDF/JSON Export)
