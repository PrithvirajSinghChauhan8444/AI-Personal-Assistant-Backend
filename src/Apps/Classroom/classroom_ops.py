from googleapiclient.discovery import build
from CoreFunctions.auth_utils import get_valid_credentials
import json

def get_classroom_service(account: str = "personal"):
    """Authenticates and returns the Google Classroom API service for a specific account."""
    creds = get_valid_credentials(account)
    if not creds:
        raise Exception(f"Google API credentials authentication failed for account '{account}'.")
    return build('classroom', 'v1', credentials=creds)

def list_courses(account: str = "personal") -> dict:
    """
    Lists the courses that the user is enrolled in or is teaching.
    Paginates to fetch all active courses and supports merging 'personal' and 'college' if account='both'.
    
    Args:
        account (str): The specific account ('personal', 'college', or 'both').
    """
    if account == "both":
        courses_merged = []
        seen_ids = set()
        
        # Query personal
        try:
            res_personal = list_courses(account="personal")
            if "courses" in res_personal:
                for c in res_personal["courses"]:
                    if c["id"] not in seen_ids:
                        courses_merged.append(c)
                        seen_ids.add(c["id"])
        except Exception as e:
            print(f"Personal account course fetch failed: {e}")
            
        # Query college
        try:
            res_college = list_courses(account="college")
            if "courses" in res_college:
                for c in res_college["courses"]:
                    if c["id"] not in seen_ids:
                        courses_merged.append(c)
                        seen_ids.add(c["id"])
        except Exception as e:
            print(f"College account course fetch failed: {e}")
            
        return {
            "account": "both",
            "count": len(courses_merged),
            "courses": courses_merged
        }

    try:
        service = get_classroom_service(account)
        course_list = []
        page_token = None
        
        while True:
            # Fetch active courses with pagination
            results = service.courses().list(
                courseStates='ACTIVE',
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            courses = results.get('courses', [])
            for course in courses:
                course_list.append({
                    "id": course.get('id'),
                    "name": course.get('name'),
                    "section": course.get('section', ''),
                    "description": course.get('descriptionHeading', ''),
                    "alternateLink": course.get('alternateLink', '')
                })
                
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        return {
            "account": account,
            "count": len(course_list),
            "courses": course_list
        }
    except Exception as e:
        print(f"Error fetching Google Classroom courses for {account}: {e}")
        return {"error": str(e)}

def list_coursework(course_id: str, account: str = "personal") -> dict:
    """
    Lists all coursework (assignments) for a specific Classroom course.
    Paginates to ensure all items are successfully retrieved.
    
    Args:
        course_id (str): The unique ID of the Google Classroom course.
        account (str): The specific account ('personal', 'college', or 'both').
    """
    if account == "both":
        res_personal = list_coursework(course_id, account="personal")
        if "error" not in res_personal:
            return res_personal
        res_college = list_coursework(course_id, account="college")
        return res_college

    try:
        service = get_classroom_service(account)
        assignment_list = []
        page_token = None
        
        while True:
            results = service.courses().courseWork().list(
                courseId=course_id,
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            coursework_items = results.get('courseWork', [])
            for item in coursework_items:
                due_date = item.get('dueDate', {})
                due_time = item.get('dueTime', {})
                formatted_due = ""
                if due_date:
                    formatted_due = f"{due_date.get('day')}/{due_date.get('month')}/{due_date.get('year')}"
                    if due_time:
                        formatted_due += f" at {due_time.get('hours')}:{due_time.get('minutes', '00')}"
                
                assignment_list.append({
                    "id": item.get('id'),
                    "title": item.get('title'),
                    "description": item.get('description', ''),
                    "alternateLink": item.get('alternateLink', ''),
                    "dueDate": formatted_due,
                    "maxPoints": item.get('maxPoints', None),
                    "state": item.get('state', '')
                })
                
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        return {
            "account": account,
            "courseId": course_id,
            "count": len(assignment_list),
            "assignments": assignment_list
        }
    except Exception as e:
        print(f"Error fetching coursework for course {course_id} on {account}: {e}")
        return {"error": str(e)}

def list_announcements(course_id: str, account: str = "personal") -> dict:
    """
    Lists the announcements for a specific Classroom course.
    Paginates to ensure all items are successfully retrieved.
    
    Args:
        course_id (str): The unique ID of the Google Classroom course.
        account (str): The specific account ('personal', 'college', or 'both').
    """
    if account == "both":
        res_personal = list_announcements(course_id, account="personal")
        if "error" not in res_personal:
            return res_personal
        res_college = list_announcements(course_id, account="college")
        return res_college

    try:
        service = get_classroom_service(account)
        announcement_list = []
        page_token = None
        
        while True:
            results = service.courses().announcements().list(
                courseId=course_id,
                pageSize=100,
                pageToken=page_token
            ).execute()
            
            announcements = results.get('announcements', [])
            for item in announcements:
                announcement_list.append({
                    "id": item.get('id'),
                    "text": item.get('text', ''),
                    "alternateLink": item.get('alternateLink', ''),
                    "creationTime": item.get('creationTime', '')
                })
                
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        return {
            "account": account,
            "courseId": course_id,
            "count": len(announcement_list),
            "announcements": announcement_list
        }
    except Exception as e:
        print(f"Error fetching announcements for course {course_id} on {account}: {e}")
        return {"error": str(e)}

def get_coursework_details(course_id: str, coursework_id: str, account: str = "personal") -> dict:
    """
    Retrieves full details for a specific coursework (assignment) item.
    
    Args:
        course_id (str): The Classroom course ID.
        coursework_id (str): The specific assignment ID.
        account (str): The specific account ('personal', 'college', or 'both').
    """
    if account == "both":
        res_personal = get_coursework_details(course_id, coursework_id, account="personal")
        if "error" not in res_personal:
            return res_personal
        res_college = get_coursework_details(course_id, coursework_id, account="college")
        return res_college

    try:
        service = get_classroom_service(account)
        item = service.courses().courseWork().get(courseId=course_id, id=coursework_id).execute()
        
        due_date = item.get('dueDate', {})
        due_time = item.get('dueTime', {})
        formatted_due = ""
        if due_date:
            formatted_due = f"{due_date.get('day')}/{due_date.get('month')}/{due_date.get('year')}"
            if due_time:
                formatted_due += f" at {due_time.get('hours')}:{due_time.get('minutes', '00')}"
                
        return {
            "account": account,
            "id": item.get('id'),
            "title": item.get('title'),
            "description": item.get('description', ''),
            "alternateLink": item.get('alternateLink', ''),
            "dueDate": formatted_due,
            "maxPoints": item.get('maxPoints', None),
            "creationTime": item.get('creationTime', ''),
            "state": item.get('state', '')
        }
    except Exception as e:
        print(f"Error fetching coursework details for item {coursework_id} on {account}: {e}")
        return {"error": str(e)}
