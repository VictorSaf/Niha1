# 0070 – Referral invitation with NDA link

## Summary

Invitația Troducer către introducer include acum un link către PDF-ul NDA servit de platformă, fără atașament de fișier. Userul primește email cu link de descărcare NDA + link spre formular.

## Implementation quality

Implementarea respectă cerințele:
- `send_referral_invitation` acceptă parametrul `nda_download_url` (optional)
- Template-ul `referral_invitation.html` afișează secțiunea NDA doar când `nda_download_url` e prezent
- `introducer.py` construiește `nda_download_url` din `invitation_link_base_url` + `/api/v1/contact/nda-template`
- Sample context actualizat pentru Settings preview

## Issues found

| Severity | Issue | File | Line |
|----------|-------|------|------|
| Minor | URL-ul NDA presupune că frontend-ul proxy-uiește `/api` către backend; dacă API e pe alt domeniu, link-ul va fi greșit | introducer.py | nda_download_url |

**Critical**: 0  
**Major**: 0  
**Minor**: 1 (documentat, acceptabil pentru setup curent)

## Recommendations

- Dacă API și frontend sunt pe domenii diferite, adăugați `api_base_url` în MailConfig și folosiți-l pentru NDA URL
- Verificare că `uploads/nda/NDA-Niha-signed.pdf` există în deployment

## Verification

- Email lifecycle tests: 19 passed
- Backward compatibility: `nda_download_url=None` → secțiunea NDA nu apare (jinja `{% if nda_download_url %}`)
