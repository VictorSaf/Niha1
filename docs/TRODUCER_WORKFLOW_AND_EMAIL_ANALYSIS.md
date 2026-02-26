# Troducer → INTRODUCER: Workflow, Client Journey & Email Templates

Analiză detaliată a fluxului de la rolul **TRODUCER** (sau cerere introducer) până la **INTRODUCER** final, incluzând șabloanele de email pentru confirmări și linkuri de actualizare rol. Pentru simulări se recomandă **adrese @yopmail.com** (inbox public, fără parolă).

---

## 1. Roluri și tranziții relevante

| Rol | Descriere |
|-----|-----------|
| **TRODUCER** | Cont creat de admin (Backoffice → Users → Create User) cu parolă; are deja acces la dashboard introducer, referral code. Poate trimite link-uri cu `?ref=<referral_code>` către pagina introducer. |
| **PREINTRODUCER** | Creat automat la submit formular introducer **fără** NDA upload (`POST /contact/introducer-request`). Primește email cu NDA PDF + link setup parolă. După setare parolă și upload NDA semnat, admin aprobă → INTRODUCER. |
| **INTRODUCER** | Rol final: NDA aprobat, `is_active=true`, acces la `/introducer/dashboard`, referral codes, comisioane. |

**Tranziții:**

- **— → PREINTRODUCER**: Submit formular pe `/introducer?ref=<code>` (buton NDA) → `POST /contact/introducer-request` (fără fișier NDA) → user creat cu `role=PREINTRODUCER`, `is_active=false`, `invitation_token` setat → email **introducer_nda_invitation** trimis.
- **PREINTRODUCER → INTRODUCER**: User deschide link din email → setup parolă → upload NDA → admin apasă "Approve NDA" (`PUT /admin/introducer/{user_id}/approve-nda`) → `user.role=INTRODUCER`, `nda_signed=true`, `is_active=true` → email **introducer_approved** trimis.

*(Alternativ: cerere introducer **cu** NDA upload pe formular → ContactRequest cu `user_role=NDA`, `request_flow=introducer`; admin Accept NDA → Approve & Create User cu `target_role=INTRODUCER` — flux diferit, fără PREINTRODUCER.)*

---

## 2. Client journey (pas cu pas)

### 2.1 Troducer (utilizator existent)

1. Login cu credențiale Troducer (ex. `tr2@yopmail.com`).
2. Redirect la `/troducer` (sau `/introducer/dashboard` după login, în funcție de rutare).
3. Pe dashboard: **referral code** vizibil (același ca în DB: `users.referral_code`).
4. Troducer trimite link: `https://<frontend>/introducer?ref=<REFERRAL_CODE>` (URL-encoding pentru caractere speciale: `$`→`%24`, `!`→`%21`, `#`→`%23`, `@`→`%40`).

### 2.2 Prospect (invitat)

1. Deschide link-ul cu `ref=...`.
2. Pagină Introducer: butoane **ENTER** (login) și **NDA** (formular cerere).
3. Click **NDA** → formular: Entity Name, Corporate Email, First Name, Last Name, Position; opțional upload NDA.
4. Submit **fără** NDA → backend creează `ContactRequest` + **User PREINTRODUCER** (dacă email nou) + trimite email **introducer_nda_invitation** (cu PDF NDA atașat și link setup parolă).

### 2.3 PREINTRODUCER (după primul email)

1. Primește email **"Introducer Programme - NDA & Account Setup - Nihao Group"**.
2. Conținut: NDA atașat (PDF), instrucțiuni: descarcă NDA, semnează, apasă buton pentru setup parolă și upload.
3. **Link din email**: `{{ base_url }}/setup-password?token={{ invitation_token }}`.  
   - `base_url` vine din MailConfig (`invitation_link_base_url`) sau default `http://localhost:5173`.
   - Link expiră în `expiry_days` (default 14 zile).

### 2.4 Setup parolă și upload NDA

1. User deschide link → pagina **Setup Password** (`/setup-password?token=...`).
2. Setează parolă + confirmă → submit.
3. După succes: redirect / pagină următoare cu **Upload Signed NDA** (file input + submit).
4. Upload NDA → backend salvează pe user; request-ul rămâne vizibil în Backoffice pentru admin.

### 2.5 Admin aprobă NDA

1. Admin: Backoffice → Onboarding → Requests (sau tab Introducer).
2. Găsește cererea pentru email-ul PREINTRODUCER (ex. `e2e-auto@yopmail.com`).
3. Apasă **"Approve NDA"** (aria-label: "Approve NDA for &lt;Entity Name&gt;").
4. Backend: `PUT /admin/introducer/{user_id}/approve-nda` → user devine INTRODUCER, `nda_signed=true`, `is_active=true` → trimite email **introducer_approved**.

### 2.6 INTRODUCER (final)

1. User primește email **"NDA Approved - Welcome to the Introducer Programme - Nihao Group"**.
2. Link în email: **"Go to Introducer Portal"** → `{{ base_url }}/introducer/dashboard`.
3. Login cu email + parola setată anterior → acces la dashboard introducer, referral codes, comisioane.

---

## 3. Email templates – confirmări și linkuri pentru role update

### 3.1 Introducer NDA Invitation (după submit formular fără NDA)

| Câmp | Valoare |
|------|--------|
| **Template** | `backend/templates/emails/introducer_nda_invitation.html` |
| **Metodă** | `email_service.send_introducer_nda_invitation(to_email, first_name, invitation_token, nda_pdf_path, expiry_days=14, mail_config)` |
| **Apelat din** | `contact.py`: după crearea user PREINTRODUCER la `POST /contact/introducer-request` (fără NDA); `admin.py`: la "Send NDA" pentru cerere introducer (când admin creează manual user și trimite NDA). |

**Variabile template:**

- `name` — first_name
- `setup_url` — `{base_url}/setup-password?token={invitation_token}` (link pentru setare parolă + pași următori)
- `expiry_days` — 14 (sau din MailConfig)

**Link pentru role update:** `setup_url` → utilizatorul devine activ după setarea parolei și upload NDA; rolul se actualizează la INTRODUCER la **Approve NDA** (nu la click pe link).

**Atașament:** NDA PDF (`Nihao_Group_NDA.pdf`).

---

### 3.2 Introducer Approved (după aprobare NDA admin)

| Câmp | Valoare |
|------|--------|
| **Template** | `backend/templates/emails/introducer_approved.html` |
| **Metodă** | `email_service.send_introducer_approved(to_email, first_name, mail_config)` |
| **Apelat din** | `admin.py`: în `approve_introducer_nda` după ce user (PREINTRODUCER/TRODUCER) este trecut la INTRODUCER. |

**Variabile template:**

- `name` — first_name
- `dashboard_url` — `{base_url}/introducer/dashboard` (link către portalul Introducer)

**Link:** buton "Go to Introducer Portal" → confirmare că rolul este deja INTRODUCER și poate folosi dashboard-ul.

---

### 3.3 Troducer Welcome (cont TRODUCER creat de admin cu parolă)

| Câmp | Valoare |
|------|--------|
| **Template** | `backend/templates/emails/troducer_welcome.html` |
| **Metodă** | `email_service.send_troducer_welcome(to_email, first_name, mail_config)` |
| **Apelat din** | `admin.py`: în `create_user` când admin creează user cu rol TRODUCER **și** parolă setată (nu se trimite și invitation). |

**Variabile template:**

- `name` — first_name
- `login_url` — `{base_url}/login` (nu schimbă rolul; confirmă că contul TRODUCER este gata de folosit)

---

### 3.4 Pre-NDA (buyer flow – pentru comparație)

- **pre_nda_invitation.html** — trimis la "Send NDA" pentru cereri **buyer** PRE_NDA; link `setup_url` pentru parolă + upload NDA.
- **pre_nda_approved.html** — trimis după aprobare NDA pentru user PRE_NDA → rol NDA; link `login_url` către login.

*(Nu fac parte din fluxul Troducer → INTRODUCER, dar folosesc același pattern: link setup/login pentru confirmare.)*

---

### 3.5 Alte template-uri cu linkuri (referință)

- **invitation.html** — link generic `setup_url` (invitație platformă, nu specific introducer).
- **magic_link.html** — autentificare magic link; nu schimbă rolul.
- **referral_invitation.html** — trimis de introducer către prospect; `invitation_url` conține ref/invite pentru pagina de contact.

---

## 4. Simulări cu Yopmail

### 4.1 De ce Yopmail

- Inbox **public**: `https://yopmail.com` → introduci `adresa@yopmail.com` (fără parolă) și vezi toate emailurile.
- Util pentru E2E: același email poate fi folosit în frontend (submit form) și verificat în Yopmail pentru linkuri (setup-password, introducer dashboard).
- Nu necesită cont sau SMTP real pentru a verifica că linkurile s-au generat corect (dacă mail-ul este trimis prin Resend/SMTP către Yopmail).

### 4.2 Adrese recomandate pentru scenarii

| Scenariu | Email | Utilizare |
|----------|--------|-----------|
| Troducer (login) | `tr2@yopmail.com` | Credențiale în `agent/scenarios/troducer_flow.py` și `agent/run_troducer.py`. |
| Prospect / PREINTRODUCER | `e2e-auto@yopmail.com` | Formular introducer; primește introducer_nda_invitation; setup parolă + upload NDA; după approve primește introducer_approved. |
| Admin | `admin@nihaogroup.com` | Nu e Yopmail; folosit pentru login backoffice. |
| Test generic | `<orice>@yopmail.com` | Ex: `test-intro-1@yopmail.com` pentru simulări manuale. |

### 4.3 Ce verifici în Yopmail

1. **După submit form introducer (fără NDA):** email "Introducer Programme - NDA & Account Setup" → prezența linkului "Set Up Password & Upload Signed NDA" (`.../setup-password?token=...`) și a atașamentului PDF.
2. **După Approve NDA (admin):** email "NDA Approved - Welcome to the Introducer Programme" → link "Go to Introducer Portal" (`.../introducer/dashboard`).
3. **Troducer creat de admin (cu parolă):** email "Your Troducer Account is Ready" → link "Go to Introducer Portal" (`.../login`).

Base URL-ul din linkuri vine din **MailConfig** (`invitation_link_base_url`); în dev poate fi `http://localhost:5173` dacă nu e setat altceva.

---

## 5. Flux rezumat (diagramă)

```
[TRODUCER]
    │
    │ share link /introducer?ref=<CODE>
    ▼
[Prospect] → click NDA → form (email, name, …) → Submit (no NDA)
    │
    │ POST /contact/introducer-request
    │ → User PREINTRODUCER created
    │ → Email: introducer_nda_invitation (setup_url + NDA PDF)
    ▼
[PREINTRODUCER]
    │
    │ open setup_url → set password → upload NDA
    ▼
[Admin] → Backoffice → Onboarding → "Approve NDA" for user
    │
    │ PUT /admin/introducer/{user_id}/approve-nda
    │ → role=INTRODUCER, nda_signed=true, is_active=true
    │ → Email: introducer_approved (dashboard_url)
    ▼
[INTRODUCER] → login → /introducer/dashboard
```

---

## 6. Fișiere cheie (referință)

| Ce | Unde |
|----|------|
| Scenar E2E troducer | `agent/scenarios/troducer_flow.py`, `agent/run_troducer.py` |
| Creare PREINTRODUCER + trimitere email | `backend/app/api/v1/contact.py` (introducer-request) |
| Aprobare NDA PREINTRODUCER → INTRODUCER | `backend/app/api/v1/admin.py` → `approve_introducer_nda` |
| Email service (send_*) | `backend/app/services/email_service.py` |
| Template-uri introducer/troducer | `backend/templates/emails/introducer_nda_invitation.html`, `introducer_approved.html`, `troducer_welcome.html` |
| Tranziții rol | `docs/ROLE_TRANSITIONS.md` |

---

*Document generat pentru verificarea workflow-ului și a emailurilor; simulări recomandate cu adrese @yopmail.com.*
