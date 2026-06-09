---
name: email-security-notification-analysis
description: "Analyzes emails retrieved from a specified account to determine the sender's legitimacy, the nature of the communication (e.g., security alert, marketing), and extracts actionable security advice."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    category: information-retrieval
    tags: []
---
# Email Security Notification Analysis

## When to Use
Use this skill when you need to execute workflows related to .

## Procedure
1. Search the specified email account for emails containing keywords related to the target service (e.g., 'Spotify', 'Developer').
2. Analyze the retrieved email content to identify the sender, subject, and body.
3. Classify the communication's nature (e.g., security alert, general notification).
4. Extract and summarize any explicit security recommendations provided in the email for the user to follow.