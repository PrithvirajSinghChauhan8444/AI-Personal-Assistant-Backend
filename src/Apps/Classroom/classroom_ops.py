from googleapiclient.discovery import build
from CoreFunctions.auth_utils import get_valid_credentials

def get_classroom_service(account: str = "personal"):
    """Authenticates and returns the Google Classroom API service for a specific account."""
    creds = get_valid_credentials(account)
    if not creds:
        raise Exception(f"Google API credentials authentication failed for account '{account}'.")
    return build('classroom', 'v1', credentials=creds)

def list_courses(account: str = "personal") -> dict:
    """
    Lists the courses that the user is enrolled in or is teaching.
    
    Args:
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_classroom_service(account)
        # Fetch active courses
        results = service.courses().list(courseStates='ACTIVE').execute()
        courses = results.get('courses', [])
        
        course_list = []
        for course in courses:
            course_list.append({
                "id": course.get('id'),
                "name": course.get('name'),
                "section": course.get('section', ''),
                "description": course.get('descriptionHeading', ''),
                "alternateLink": course.get('alternateLink', '')
            })
            
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
    Lists the coursework (assignments) for a specific Classroom course.
    
    Args:
        course_id (str): The unique ID of the Google Classroom course.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_classroom_service(account)
        results = service.courses().courseWork().list(courseId=course_id).execute()
        coursework_items = results.get('courseWork', [])
        
        assignment_list = []
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
    
    Args:
        course_id (str): The unique ID of the Google Classroom course.
        account (str): The specific account ('personal' or 'college').
    """
    try:
        service = get_classroom_service(account)
        results = service.courses().announcements().list(courseId=course_id).execute()
        announcements = results.get('announcements', [])
        
        announcement_list = []
        for item in announcements:
            announcement_list.append({
                "id": item.get('id'),
                "text": item.get('text', ''),
                "alternateLink": item.get('alternateLink', ''),
                "creationTime": item.get('creationTime', '')
            })
            
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
        account (str): The specific account ('personal' or 'college').
    """
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
