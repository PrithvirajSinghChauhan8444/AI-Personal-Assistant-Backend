
messages:

- - id:
    - langchain
    - schema
    - messages
    - SystemMessage
      kwargs:
      content: |
      You are GmailWorker. You manage email fetching, searching, and sending. CRITICAL: You MUST always output your reasoning and intermediate thought process in natural language BEFORE calling any tools. Never invoke tools silently.### 🚨 HUMAN-IN-THE-LOOP (HITL) PROTOCOL:

      You have access to the `request_human_intervention` tool. You MUST call this tool immediately to pause execution and request manual help from the human user in the following scenarios:

      1. **Authentication, Login & 2FA**: If you require credentials, passwords, 2FA/OTP codes, API keys, OAuth approval, or if you hit CAPTCHAs, bot blocks, or verification screens.
      2. **Permissions & System Prompts**: If you encounter 'Permission Denied' errors, a `sudo` password request, or system security blocks.
      3. **Potentially Destructive Actions**: If you need to delete files, overwrite code, terminate critical processes, or make system-wide changes, and need confirmation.
      4. **Roadblocks & Ambiguities**: If tools fail repeatedly, if you get stuck, or if the task instructions are ambiguous.
      5. **User Manual Control**: If the user requests to perform an action manually or asks you to pause and wait.
         Always explain the exact reason for pausing when calling the tool.
         type: system
         lc: 1
         type: constructor
  - id:
    - langchain
    - schema
    - messages
    - HumanMessage
      kwargs:
      content: |-

      Task: Fetch the 5 most recent emails from Gmail.

      Working Memory (Data from previous tasks):
      {
      "previous_session_summary": "The user requested a system status check, which was completed by pinging all background workers and verifying connectivity. The assistant confirmed that all systems are operational, successfully synced the user's GitHub profile, and retrieved data for 19 active college courses and Gmail integration.",
      "task_3": "The ping signal has been received and processed. Connectivity is verified.\n\n**System Status:**\n*   **Current Time:** 12:55 AM, Monday, June 15, 2026\n*   **ProductivityWorker Status:** Operational and ready for tasks.",
      "task_7": "The ping signal has been successfully sent to the GitHub API. I have verified connectivity by retrieving the profile information for the authenticated user, **PrithvirajSinghChauhan8444**.\n\n**Connectivity Status:** Verified\n**Authenticated User:** Prithvi Raj Singh Chauhan\n**GitHub Profile URL:** [https://github.com/PrithvirajSinghChauhan8444](https://github.com/PrithvirajSinghChauhan8444)\n**Account Created:** 2025-03-06\n**Public Repositories:** 7",
      "task_4": "I see you have provided a list of available tools and a set of instructions, but you have not given me a specific task or question to perform.\n\nPlease tell me what you would like me to do! For example, you could ask me to:\n\n1.  **Analyze** a specific scenario using the available tools.\n2.  **Compare** two different tools for a given task.\n3.  **Execute** a multi-step process.\n\nOnce you provide a goal, I will use the appropriate tools to help you achieve it.",
      "task_2": "The ping signal has been successfully sent and processed. Connectivity to the `ClassroomWorker` is verified.\n\n**Status Summary:**\n*   **Personal Account:** No courses found.\n*   **College Account:** Successfully retrieved 19 active courses (e.g., *ES-II*, *Machine Learning 2026*, *Digital Signal Processing*, *DBMS-I*, etc.).\n\nThe system is fully operational and ready for further classroom-related tasks.",
      "task_8": "The ping signal has been successfully processed. MiscWorker is online and fully operational.",
      "task_1": "The ping signal has been successfully sent to verify connectivity. The email was sent to `prithvirajsinghchauhan8444@gmail.com` (Message ID: `19ec79f12322d1ab`), confirming that the GmailWorker is now operational.",
      "task_5": "The connectivity ping has been verified through the system health check. \n\n**System Status Report:**\n*   **SystemWorker Connectivity:** Verified (Operational)\n*   **CPU Usage:** 11.1%\n*   **RAM Usage:** 80.9%\n*   **Disk Usage:** 44.2%\n*   **Battery Status:** 79.5% (Discharging)\n\nThe system is currently online and functioning within normal parameters.",
      "task_6": "The `BrowserWorker` has been successfully pinged and its operational status has been verified.\n\n### **BrowserWorker Status Report**\n*   **Operational State:** The `BrowserWorker` is currently in an **\"Activated\"** state.\n*   **Connectivity:** The communication channel between the main thread and the worker is confirmed to be open and responsive.\n*   **Conclusion:** The `BrowserWorker` is fully operational and functioning as an event-driven background process. No further action is required.",
      "active_skills": [
      "---\nname: email-content-search-and-extraction\ndescription: \"Searches a specified email inbox (or simulated inbox) using keywords or sender domains to locate relevant messages.\"\nversion: 1.0.0\nplatforms: [linux]\nmetadata:\n  hermes:\n    category: GmailWorker\n    tags: []\n---\n# Email Content Search And Extraction\n\n## When to Use\nUse this skill when you need to execute workflows related to .\n\n## Procedure\n1. Specify the target email address or inbox context. 2. Define the search criteria (keywords, sender domains, etc.). 3. Execute the search operation against the inbox data. 4. Analyze the returned emails to extract relevant content based on the search criteria.",
      "---\nname: email-security-notification-analysis\ndescription: \"Analyzes emails retrieved from a specified account to determine the sender's legitimacy, the nature of the communication (e.g., security alert, marketing), and extracts actionable security advice.\"\nversion: 1.0.0\nplatforms: [linux]\nmetadata:\n  hermes:\n    category: GmailWorker\n    tags: []\n---\n# Email Security Notification Analysis\n\n## When to Use\nUse this skill when you need to execute workflows related to .\n\n## Procedure\n1. Search the specified email account for emails containing keywords related to the target service (e.g., 'Spotify', 'Developer').\n2. Analyze the retrieved email content to identify the sender, subject, and body.\n3. Classify the communication's nature (e.g., security alert, general notification).\n4. Extract and summarize any explicit security recommendations provided in the email for the user to follow."
      ],
      "skills_index": [
      "system-process-status-and-launch",
      "spotify-playback-control",
      "system-worker-status-check",
      "email-content-search-and-extraction",
      "email-security-notification-analysis",
      "file-to-email-transfer",
      "github-private-repo-readme-retrieval",
      "github-repository-data-extraction",
      "browser-based-knowledge-retrieval",
      "browser-linkedin-navigation",
      "multi-agent-project-documentation-retrieval",
      "memory-state-management",
      "local-script-execution-and-result-capture",
      "file-download-and-storage",
      "youtube-music-control",
      "linkedin-content-drafting-and-refinement"
      ],
      "user_profile": {
      "name": "User",
      "preferences": [],
      "favorite_city": "Dehradun",
      "brother_name": "Rohan",
      "mail": "testing_user@example.com"
      },
      "relevant_memories": [
      "The user's personal email address is prithvirajsinghchauhan8444@gmail.com.",
      "The user uses Google Classroom for academic updates and coursework management, and is enrolled in courses including Machine Learning 2026 (taught by Dr. Abhishek Sharma), Embedded Systems II, Digital Signal Processing, and Entrepreneurship (taught by Amit Agrawal).",
      "The user is a B.Tech student in Electronics and Communication Engineering (ECE) at IIITNR Naya Raipur, batch 2024-2028."
      ]
      }

      IMPORTANT NOTE ON LARGE DATA:
      If any entry in the Working Memory contains a `"__file_reference__"`, the actual large data has been saved to that local file path to avoid context bloat. You can directly read the content of that file using your file-reading tools (like `read_file_tool` or running python/terminal commands), copy/move the file, or use the file path as an attachment/input for other tools.

      Execute the tools necessary to complete this task. Return a concise, data-rich summary of your findings or actions.

      ### Specialized Skills for GmailWorker:

      Use the following step-by-step procedures when resolving tasks in your domain:

      ## Skill: email-content-search-and-extraction - Searches a specified email inbox (or simulated inbox) using keywords or sender domains to locate relevant messages.

      # Email Content Search And Extraction

      ## When to Use

      Use this skill when you need to execute workflows related to .

      ## Procedure


      1. Specify the target email address or inbox context. 2. Define the search criteria (keywords, sender domains, etc.). 3. Execute the search operation against the inbox data. 4. Analyze the returned emails to extract relevant content based on the search criteria.

      ---

      ## Skill: email-security-notification-analysis - Analyzes emails retrieved from a specified account to determine the sender's legitimacy, the nature of the communication (e.g., security alert, marketing), and extracts actionable security advice.

      # Email Security Notification Analysis

      ## When to Use

      Use this skill when you need to execute workflows related to .

      ## Procedure

      1. Search the specified email account for emails containing keywords related to the target service (e.g., 'Spotify', 'Developer').
      2. Analyze the retrieved email content to identify the sender, subject, and body.
      3. Classify the communication's nature (e.g., security alert, general notification).
      4. Extract and summarize any explicit security recommendations provided in the email for the user to follow.

      ---

      ## Skill: file-to-email-transfer - Transfers a local file from a specified path to a target email address.

      # File To Email Transfer

      ## When to Use

      Use this skill when you need to execute workflows related to .

      ## Procedure

      1. Identify the source file path provided by the user. 2. Identify the target email address. 3. Use the internal file system access tool to locate the file at the source path. 4. Use the email sending tool to attach the located file and send the message to the target email address.
         id: 7cca64bc-0a68-4601-b050-f1dc987998d3
         type: human
         lc: 1
         type: constructor
