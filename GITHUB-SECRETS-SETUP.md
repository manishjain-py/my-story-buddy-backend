# GitHub Repository Secrets Setup

For automatic deployment to work, you need to configure the following secrets in your GitHub repository.

## How to Add Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret below

---

## Required Secrets

### AWS Infrastructure
```
AWS_ACCESS_KEY_ID
Your AWS access key ID for deployment
Example: AKIAIOSFODNN7EXAMPLE
```

```
AWS_SECRET_ACCESS_KEY
Your AWS secret access key for deployment
Example: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

```
EC2_HOST
Your EC2 instance public IP address
Current Value: 204.236.220.17
```

```
EC2_SSH_KEY
Contents of your SSH private key file (my-story-buddy-key.pem)
Copy the entire contents including:
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
```

### Application Configuration
```
OPENAI_API_KEY
Your OpenAI API key for story and image generation
Example: sk-...
```

### Database Configuration
```
DATABASE_HOST
Your RDS database hostname
Example: database-1.cbuyybcooluu.us-west-2.rds.amazonaws.com
```

```
DATABASE_USER
Your database username
Example: admin
```

```
DATABASE_PASSWORD
Your database password
Example: your-secure-password
```

```
DATABASE_NAME
Your database name
Example: mystorybuddy
```

### Authentication Configuration
```
GOOGLE_CLIENT_ID
Your Google OAuth client ID
Example: 123456789-abcdefghijklmnop.apps.googleusercontent.com
```

```
GOOGLE_CLIENT_SECRET
Your Google OAuth client secret
Example: GOCSPX-abcdefghijklmnopqrstuvwxyz
```

```
GOOGLE_REDIRECT_URI
Your Google OAuth redirect URI
Example: http://204.236.220.17/auth/google/callback
```

```
FRONTEND_URL
Your frontend application URL
Example: https://www.mystorybuddy.com
```

```
JWT_SECRET_KEY
Secret key for JWT token signing (generate a random 64-character string)
Example: your-super-secret-jwt-key-64-characters-long-and-random-string
```

---

## How to Get These Values

### AWS Credentials
1. Go to AWS Console → IAM → Users → Your User
2. Security credentials → Create access key
3. Choose "Application running outside AWS"
4. Copy Access Key ID and Secret Access Key

### EC2 SSH Key
```bash
# View your SSH key content
cat /path/to/my-story-buddy-key.pem
```

### Database Configuration
Check your RDS instance settings in AWS Console → RDS

### Google OAuth Configuration
1. Go to Google Cloud Console → APIs & Credentials → OAuth 2.0 Client IDs
2. Copy Client ID and Client Secret

### JWT Secret Key
```bash
# Generate a random JWT secret
openssl rand -hex 32
```

---

## Verification

After adding all secrets, your GitHub repository should have these secrets configured:

✅ AWS_ACCESS_KEY_ID  
✅ AWS_SECRET_ACCESS_KEY  
✅ EC2_HOST  
✅ EC2_SSH_KEY  
✅ OPENAI_API_KEY  
✅ DATABASE_HOST  
✅ DATABASE_USER  
✅ DATABASE_PASSWORD  
✅ DATABASE_NAME  
✅ GOOGLE_CLIENT_ID  
✅ GOOGLE_CLIENT_SECRET  
✅ GOOGLE_REDIRECT_URI  
✅ FRONTEND_URL  
✅ JWT_SECRET_KEY  

---

## Testing Deployment

Once all secrets are configured:

1. Push any change to the `main` branch
2. Go to **Actions** tab in GitHub
3. Watch the "Deploy to EC2" workflow run
4. Check the deployment logs and final status

The deployment should automatically:
- Build Docker image with your latest code
- Push to ECR
- Deploy to EC2
- Run health checks
- Report success/failure

---

## Troubleshooting

**If deployment fails:**

1. Check GitHub Actions logs for specific errors
2. Verify all secrets are set correctly
3. SSH to EC2 and check container status:
   ```bash
   ssh -i my-story-buddy-key.pem ec2-user@204.236.220.17
   cd /opt/my-story-buddy
   docker-compose logs
   ```

**Common issues:**
- Missing or incorrect secrets
- SSH key formatting (must include newlines)
- AWS credentials lacking proper permissions
- Database connection issues