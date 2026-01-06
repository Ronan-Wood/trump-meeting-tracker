# 🚀 Deployment Guide - Trump Meetings Tracker

## What You're Deploying

A fully automated system that:
1. **Searches** NewsAPI + RSS feeds for Trump meetings (2x/week)
2. **Extracts** attendee names, companies, titles from articles
3. **Classifies** companies into YOUR 17 industries
4. **Prioritizes** meetings (High/Medium/Low) based on relevance
5. **Emails** beautiful HTML reports to your team

**Total Cost:** $0/month (using free tiers)

---

## 📋 Prerequisites

You need:
- [ ] GitHub account
- [ ] 10 minutes of time
- [ ] Email addresses to receive reports

---

## 🎯 Step-by-Step Deployment

### 1. Get API Keys (5 minutes)

#### A. NewsAPI (for news search)
1. Go to: https://newsapi.org/register
2. Sign up (FREE - 100 searches/day)
3. Copy your API key immediately after signup
4. Save it somewhere secure

#### B. SendGrid (for sending emails)
1. Go to: https://sendgrid.com/
2. Sign up (FREE - 100 emails/day)
3. Verify your email address
4. Go to Settings → API Keys → Create API Key
5. Name it "Trump Tracker"
6. Select "Full Access"
7. Copy the key (starts with `SG.`)
8. Save it somewhere secure

#### C. Verify Sender Email (in SendGrid)
1. Settings → Sender Authentication
2. Verify a Single Sender
3. Enter your work email
4. Fill out form and verify via email link

---

### 2. Set Up GitHub (5 minutes)

#### A. Get the Code
**Option 1: Fork (Recommended)**
1. Go to this repository on GitHub
2. Click "Fork" button (top right)
3. You now have your own copy!

**Option 2: Download & Upload**
1. Download all files from outputs folder
2. Create new GitHub repository
3. Upload files

#### B. Add Secrets
1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click "New repository secret" for each:

| Secret Name | Value | Where to Get It |
|-------------|-------|-----------------|
| `NEWS_API_KEY` | Your NewsAPI key | From Step 1A |
| `SENDGRID_API_KEY` | Your SendGrid key (SG.xxx) | From Step 1B |
| `SENDER_EMAIL` | Your verified email | From Step 1C |
| `EMAIL_RECIPIENTS` | `email1@co.com,email2@co.com` | Your team emails |

**Important:** 
- No spaces in EMAIL_RECIPIENTS
- Use commas to separate multiple emails
- Double-check spelling of secret names!

#### C. Enable GitHub Actions
1. Go to **Actions** tab
2. Click "I understand my workflows, go ahead and enable them"

---

### 3. Test It! (1 minute)

1. Go to **Actions** tab
2. Click "Trump Meetings Tracker" workflow
3. Click "Run workflow" → "Run workflow"
4. Wait ~60 seconds
5. Check your email! 📧

---

## ✅ Success Checklist

After running, you should see:
- ✅ Green checkmark in GitHub Actions
- ✅ Email in your inbox (check spam!)
- ✅ Email shows 0-10 meetings (depending on recent news)

---

## 📅 Ongoing Operation

**Automatic Schedule:**
- Runs every **Monday** at 9:00 AM UTC (4:00 AM EST)
- Runs every **Thursday** at 9:00 AM UTC (4:00 AM EST)

**What It Does:**
1. Searches last 7 days of news
2. Finds Trump meetings with executives
3. Extracts company/industry info
4. Sends prioritized email to your team

**No maintenance required!**

---

## 🔧 Customization Options

### Change Schedule
Edit `.github/workflows/tracker.yml`:
```yaml
schedule:
  # Daily at 8 AM UTC:
  - cron: '0 8 * * *'
  
  # Every weekday at 9 AM:
  - cron: '0 9 * * 1-5'
```

### Add More Companies
Edit `data_sources_config.json`:
```json
{
  "name": "3PL",
  "related_companies": [
    "XPO Logistics",
    "Your Company Here"  ← Add here
  ]
}
```

### Change Lookback Period
In GitHub Actions workflow, change `DAYS_BACK`:
```yaml
env:
  DAYS_BACK: '14'  # Look back 14 days instead of 7
```

---

## 📊 Understanding the Emails

### Priority Levels

**🔴 HIGH PRIORITY**
- Companies in YOUR industries (3PL, E-Commerce, etc.)
- High confidence match
- **Action:** Review immediately

**⚠️ MEDIUM PRIORITY**
- Companies in your industries
- Medium confidence match
- **Action:** Review when possible

**ℹ️ OTHER**
- Companies outside your focus
- Or low confidence matches
- **Action:** FYI only

### Confidence Levels

**HIGH** ✓
- Company name explicitly mentioned in article
- Well-known company in our database
- Example: "Amazon CEO Andy Jassy"

**MEDIUM** ⚡
- Company inferred from context
- Partial name match
- Example: Company name abbreviated

**LOW** ⚠️
- Uncertain company identification
- New/unknown company
- **Action:** Manual verification recommended

---

## 🐛 Troubleshooting

### No email received
1. Check spam/junk folder
2. Verify EMAIL_RECIPIENTS is correct in GitHub Secrets
3. Check SendGrid sender email is verified
4. Look at GitHub Actions logs for errors

### No meetings found
- **Normal!** Trump doesn't meet executives every day
- System searches 7 days back - may not find anything
- Will catch meetings as they're reported in news
- News has 24-48 hour delay after actual meetings

### "NewsAPI searches will be skipped"
- NEWS_API_KEY not set in GitHub Secrets
- Or key is invalid - get new one from newsapi.org

### "Error: 402 Payment Required" (NewsAPI)
- Free tier limit reached (100/day)
- Shouldn't happen at 2x/week usage
- Check if someone else is using your key

### GitHub Actions failing
1. Click on the failed run
2. Look at error message
3. Common fixes:
   - Add missing secrets
   - Check secret names are exact
   - Verify API keys are still valid

---

## 📈 Usage Limits (Free Tiers)

| Service | Free Limit | Your Usage | Safe? |
|---------|------------|------------|-------|
| NewsAPI | 100 searches/day | ~10-20/week | ✅ Yes |
| SendGrid | 100 emails/day | 2-4/week | ✅ Yes |
| GitHub Actions | 2,000 min/month | ~8-16 min/month | ✅ Yes |

**You'll never hit these limits with 2x/week usage!**

---

## 🔐 Security Best Practices

1. **Never commit API keys to GitHub**
   - Always use GitHub Secrets
   - Keys in code = security risk

2. **Rotate keys periodically**
   - Change SendGrid key every 6 months
   - Change NewsAPI key every 6 months

3. **Monitor usage**
   - Check GitHub Actions for unusual activity
   - Review SendGrid email logs monthly

4. **Limit access**
   - Only add trusted collaborators to repo
   - Review who has access to GitHub Secrets

---

## 📞 Support

### Something not working?

1. **Check GitHub Actions logs**
   - Go to Actions tab
   - Click on failed run
   - Read error message

2. **Verify all 4 secrets are set**
   - NEWS_API_KEY
   - SENDGRID_API_KEY
   - SENDER_EMAIL
   - EMAIL_RECIPIENTS

3. **Test API keys manually**
   - Try logging into NewsAPI.org
   - Try logging into SendGrid.com

4. **Still stuck?**
   - Create GitHub Issue with:
     - Error message (remove API keys!)
     - What you've tried
     - Screenshots if helpful

---

## 🎉 You're All Set!

Your Trump Meetings Tracker is now:
- ✅ Fully automated
- ✅ Searching 150,000+ news sources
- ✅ Emailing your team 2x/week
- ✅ Costing you $0/month

**Sit back and let it run!**

---

## 🔄 Updating the System

When we release updates:

1. Go to original repository
2. Check for new releases
3. If you forked:
   ```bash
   git pull upstream main
   git push origin main
   ```
4. If you downloaded:
   - Download new files
   - Replace old files
   - Keep your `data_sources_config.json` customizations

---

## 📚 Additional Resources

- **Full Documentation:** README.md
- **Quick Start:** SETUP.md
- **Code:** trump_meetings_tracker_enhanced.py
- **Configuration:** data_sources_config.json

---

**Happy Tracking! 🇺🇸📊**

*Questions? Open a GitHub Issue!*