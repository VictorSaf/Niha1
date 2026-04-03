# Reguli de tranziție: De la → La (role / status)

**Sursă unică de adevăr.** Platforma folosește DOAR aceste tranziții. Nu există schimbări arbitrare de role; fiecare tranziție este declanșată de acțiunea indicată.

| De la → La | Condiție / acțiune |
|------------|--------------------|
| **PRE_NDA → NDA** | Backoffice: Approve NDA (endpoint `PUT /admin/introducer/{user_id}/approve-nda`). User-ul PRE_NDA uploadează NDA-ul semnat, admin-ul aprobă → `user.role = NDA`, `user.nda_signed = true`, `user.is_active = true`. |
| **NDA → KYC** | Backoffice: Approve & Create User → `user.role = KYC`, `contact_request.user_role = KYC`. |
| **NDA (introducer) → INTRODUCER** | Backoffice: Approve & Create User cu `target_role=INTRODUCER` → `user.role = INTRODUCER`, `entity_id = null`, nu se creează Entity. Cererea NDA trebuie să aibă `request_flow='introducer'` (submit la `/contact/introducer-nda-request`). |
| **PREINTRODUCER → INTRODUCER** | Backoffice: Approve NDA introducer (`PUT /admin/introducer/{user_id}/approve-nda`) după ce user-ul PREINTRODUCER a încărcat NDA-ul semnat (`POST /contact/introducer/upload-nda`). Promovează la `user.role = INTRODUCER`, `nda_signed = true`. Nu există rol separat „TRODUCER” (eliminat în 0072); onboarding fără NDA folosește PREINTRODUCER (referral + Send NDA din backoffice sau flux public). |
| **KYC → REJECTED** | Backoffice: Reject KYC (apel `reject_user`). |
| **KYC → APPROVED** | Backoffice: Approve KYC (apel `approve_user`); `entity.kyc_status = APPROVED`. |
| **APPROVED → FUNDING** | La primul `announce_deposit` reușit pentru entity (în `deposit_service`). |
| **FUNDING → AML** | Backoffice confirmă primirea fondurilor: apel `confirm_deposit` (în `deposit_service`). |
| **AML → CEA** | Backoffice execută `clear_deposit` (AML cleared, entity credited). |
| **FUNDING / AML → REJECTED** | Backoffice apel `reject_deposit` (AML reject). |
| **CEA → CEA_SETTLE** | După debit EUR (ex. achiziție CEA), când `entity EUR balance = 0` (în `role_transitions`). |
| **CEA_SETTLE → SWAP** | Toate batch-urile `CEA_PURCHASE` pentru entity sunt `SETTLED` (în `transition_cea_settle_to_swap_if_all_cea_settled`). |
| **SWAP → EUA_SETTLE** | `Balance CEA = 0` (în `transition_swap_to_eua_settle_if_cea_zero`). |
| **EUA_SETTLE → EUA** | Toate batch-urile `SWAP_CEA_TO_EUA` pentru entity sunt `SETTLED` (în `transition_eua_settle_to_eua_if_all_swap_settled`). |

## Implicații

- **PRE_NDA**: Buyer referit de un Introducer care trimite formularul fără a uploada NDA-ul. ContactRequest se creează cu `user_role=PRE_NDA`. Admin apasă "Send NDA" → se creează user PRE_NDA + email cu PDF NDA + link setup password. După setarea parolei, login → `/pre-nda` (upload NDA). La upload, `ContactRequest.user_role` tranzitează de la `PRE_NDA` la `NDA`. Admin vizualizează NDA → "Accept NDA" (`nda_accepted=true`) → apoi "Approve & Create User" → user devine KYC.
- **nda_accepted gate**: Pentru buyer requests cu `user_role=NDA`, admin-ul trebuie să accepte NDA-ul (via `PUT /admin/contact-requests/{id}/accept-nda`) înainte de a putea folosi "Approve & Create User".
- **MM (Market Maker)**: Rol creat și gestionat strict de admin. Nu trece prin cereri de contact sau aprobări. Admin creează useri MM din Users (Create User, rol MM) și poate modifica rolul lor (Edit User) sau orice alt câmp.
- **PREINTRODUCER**: User cu `referral_code` unic, adesea creat când admin trimite NDA pe o cerere introducer fără NDA (`POST /admin/introducer/{request_id}/send-nda`) sau prin flux public fără NDA. `nda_signed=false` până la upload NDA + aprobare admin; redirect post-login `/preintroducer`. Codul de referral se validează ca `type: preintroducer` la `POST /contact/validate-code`. După aprobare NDA → **INTRODUCER**.
- **INTRODUCER**: Rol creat din cereri NDA cu `request_flow='introducer'` (pagina `/introducer`, endpoint `POST /contact/introducer-nda-request`). Admin aprobă din tab-ul Introducer (Backoffice → Onboarding → Introducer) cu Approve & Create User; `create-from-request` primește `target_role=INTRODUCER` și creează user fără Entity. Admin poate crea și direct un user INTRODUCER din **Backoffice → Users → Create User** (similar MM), fără cerere de contact. INTRODUCER are acces doar la `/introducer/dashboard` (conținut simplificat). Codurile de referral de la un INTRODUCER returnează `type: introducer` la validate-code (buyer NDA cu referral).
- **Contact request**: Starea se citește din `contact_request.user_role` (NDA, KYC, REJECTED). PUT contact-requests permite actualizarea `user_role`; când se setează REJECTED, userul legat (dacă există) devine REJECTED. Badge-ul în listă folosește `contact_request.user_role`.
- **User role**: Nu există endpoint pentru schimbare arbitrară de role pentru userii din flow (NDA → EUA). Tranzițiile se fac doar prin: create-from-request, approve_user, reject_user, announce_deposit, confirm_deposit, clear_deposit, reject_deposit, și funcțiile din `role_transitions`. Pentru MM, admin poate seta sau schimba rolul direct (PUT /admin/users/{id}).
- **APPROVED → FUNDING**: Doar prin primul `announce_deposit` reușit; nu există „fund user” manual.
