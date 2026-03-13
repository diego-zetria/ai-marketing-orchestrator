# WhatsApp Business Cloud API — Setup Guide

This guide covers the setup required to enable WhatsApp notifications in the Agency Approval Portal.

## 1. Setup WABA (WhatsApp Business Account)

1. Go to [Meta Business Suite](https://business.facebook.com)
2. Navigate to **Settings > Business Settings > Accounts > WhatsApp Accounts**
3. Click **Add** and follow the flow to add the WhatsApp product
4. Register and verify a phone number (must be able to receive SMS/voice for OTP)
5. Note the **Phone Number ID** from the WhatsApp Manager dashboard

## 2. Generate System User Token

1. Go to **Business Manager > Settings > System Users**
2. Create a system user (or use an existing one) with **Admin** role
3. Click **Generate New Token**
4. Select the WhatsApp Business app
5. Grant the `whatsapp_business_messaging` permission
6. Copy the token — this is your `WHATSAPP_ACCESS_TOKEN`

> **Important:** System user tokens do not expire. Store securely in AWS Parameter Store or Secrets Manager.

## 3. Create Message Templates

Submit these 3 templates in **Meta Business Manager > WhatsApp Manager > Message Templates**.

All templates use category **UTILITY** and language **pt_BR**.

### Template 1: `aprovacao_nova_arte`

| Component | Config |
|-----------|--------|
| **Header** | Type: IMAGE (dynamic) |
| **Body** | `Ola! Uma nova arte de {{1}} esta pronta para sua aprovacao: {{2}} (versao {{3}}). Clique no botao abaixo para revisar.` |
| **Button** | Type: URL, Label: `Revisar Arte`, URL: `https://approvals.example.com{{1}}` (dynamic suffix) |

### Template 2: `aprovacao_lembrete`

| Component | Config |
|-----------|--------|
| **Header** | Type: IMAGE (dynamic) |
| **Body** | `Lembrete: A arte de {{1}} — {{2}} — esta aguardando sua aprovacao ha {{3}} dias. Por favor, revise o mais breve possivel.` |
| **Button** | Type: URL, Label: `Revisar Arte`, URL: `https://approvals.example.com{{1}}` (dynamic suffix) |

### Template 3: `aprovacao_confirmada`

| Component | Config |
|-----------|--------|
| **Body** | `Obrigado! Sua decisao para a arte de {{1}} — {{2}} — foi registrada: {{3}}.` |

> No header or button for the confirmation template.

### Template Approval

- Templates typically take 1-24 hours to be approved by Meta
- Status can be checked in **WhatsApp Manager > Message Templates**
- Rejected templates need to be resubmitted with modifications

## 4. Environment Variables

Add to `samconfig.toml` (or pass as SAM parameter overrides):

```toml
"WhatsAppPhoneNumberId=YOUR_PHONE_NUMBER_ID",
"WhatsAppAccessToken=YOUR_SYSTEM_USER_TOKEN",
```

Leave empty (`""`) to disable WhatsApp notifications — email will still work.

## 5. Register Client Phone Numbers

Update clients in the database with their WhatsApp numbers in E.164 format (without `+`):

```sql
UPDATE marketing_bot.clients
SET whatsapp_phone = '5541999887766'
WHERE name = 'client_alpha';
```

Format: country code + area code + number (e.g., `55` for Brazil + `41` for Curitiba + `999887766`).

Clients without `whatsapp_phone` will only receive email notifications.

## 6. Cost Estimate

WhatsApp Business API pricing (Brazil, utility category):

| Metric | Value |
|--------|-------|
| Cost per message | ~R$0.035 (~$0.0068 USD) |
| Estimated monthly volume | ~200 messages |
| Monthly cost | ~R$7.00 (~$1.36 USD) |
| Annual cost | ~R$84.00 (~$16.30 USD) |

The first 1,000 service conversations per month are free.

## 7. Testing

### Local Testing

```bash
# Run WhatsApp service tests
pytest tests/test_whatsapp_service.py -v

# Run Lambda integration tests
pytest tests/test_approval_processor.py tests/test_approval_reminder.py -v -k whatsapp
```

### Staging Testing

1. Deploy with WhatsApp env vars set
2. Set `whatsapp_phone` for a test client in the DB
3. Move a ClickUp task to `revisao_cliente` status
4. Verify the client receives both email and WhatsApp message

## 8. Troubleshooting

| Issue | Solution |
|-------|----------|
| Template not found | Check template name and language match exactly (`pt_BR`) |
| Message not delivered | Verify phone number is in E.164 format, recipient has WhatsApp |
| 401 Unauthorized | Token expired or lacks `whatsapp_business_messaging` permission |
| Rate limited (429) | Meta allows ~80 messages/second for utility — unlikely to hit |
| WhatsApp disabled | Both env vars must be set; empty string disables the service |
