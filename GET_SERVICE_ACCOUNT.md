# 🔑 Get Google Service Account Credentials for Gemini AI

## Current Status
❌ **You have OAuth client credentials** (for web login flow)  
✅ **You need Service Account credentials** (for server-to-server API calls)

## 📋 Step-by-Step Instructions

### 1. Go to Google Cloud Console
Visit: https://console.cloud.google.com/

### 2. Select Your Project
- Current project ID from your file: **`custom-tine-464511-u1`**
- Or use the project from your code: **`gothic-guard-459415-q5`**

### 3. Enable Required APIs
1. Go to **APIs & Services** > **Library**
2. Search and enable:
   - **Vertex AI API**
   - **Generative Language API** (if available)

### 4. Create Service Account
1. Go to **IAM & Admin** > **Service Accounts**
2. Click **"+ CREATE SERVICE ACCOUNT"**
3. Fill in:
   - **Name**: `gemini-api-service`
   - **Description**: `Service account for Gemini AI API`
4. Click **"CREATE AND CONTINUE"**

### 5. Add Roles
Add these roles to the service account:
- **Vertex AI User** 
- **ML Developer** (if available)
- **Generative AI Administrator** (if available)

### 6. Create Key
1. Click on the newly created service account
2. Go to **"Keys"** tab
3. Click **"ADD KEY"** > **"Create new key"**
4. Select **"JSON"** format
5. Click **"CREATE"**
6. **Download the JSON file** - this is what we need!

### 7. Verify the Service Account File
The service account JSON should look like this:
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "gemini-api-service@your-project.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

## 🚀 Once You Have the Service Account File

1. **Save it securely** (don't commit to git)
2. **Let me know** and I'll help you:
   - Set it up for local testing
   - Upload to Render for production
   - Test the Gemini AI functionality

## ⚠️ Important Notes

- **Don't share** the service account file (contains private keys)
- **Use different projects** for development vs production if needed
- **The file should have** `"type": "service_account"` not `"web"`

## 🆘 Need Help?
If you run into issues:
1. Make sure you're the owner/admin of the Google Cloud project
2. Check that billing is enabled for the project
3. Ensure the APIs are enabled before creating the service account