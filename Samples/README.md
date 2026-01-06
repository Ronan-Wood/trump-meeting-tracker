# Sample Files

This folder contains sample outputs from the Trump Meetings Tracker.

## Files

### sample_trump_meetings.xlsx
A realistic example of the Excel report that will be attached to your emails.

**What's inside:**
- **Dashboard Sheet** (opens by default)
  - Summary Statistics: Total meetings, attendees, unique companies, date range
  - Bar Chart: Top 10 Industries represented in meetings
  - Pie Chart: Confidence level distribution (High/Medium/Low)
  - Top 10 Companies table
  - Meetings by Location breakdown

- **Meeting Data Sheet**
  - Complete detailed table with all meeting information
  - Color-coded rows:
    - 🟢 Green = High confidence
    - 🟡 Yellow = Medium confidence
    - 🔴 Red = Low confidence (requires manual review)
  - Columns: Date, Location, Meeting Type, Attendee Name, Title, Company, Primary Industry, Confidence Level, Source Publication, Source URL, Notes

### email_preview.html
Sample HTML email showing what the email body will look like. The email shows recent meetings from the last 7 days, while the Excel attachment contains the complete historical log.

## How It Works

Every Monday and Thursday, the script will:
1. Search news sources for Trump meetings
2. Save new meetings to database (auto-deduplicated)
3. Generate a fresh Excel file with ALL historical meetings
4. Send email with recent meetings + complete Excel attachment

The sample file contains 14 realistic test meetings to demonstrate the layout and features.
