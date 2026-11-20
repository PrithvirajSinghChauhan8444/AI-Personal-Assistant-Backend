package workspace

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"

	"assistant/src/tools"
)

const (
	defaultClassroomPageLimit = 20
	maxClassroomPageLimit     = 100
	classroomAPIBaseURL       = "https://classroom.googleapis.com/v1"
)

// ClassroomListCoursesArgs represents arguments for classroom_list_courses.
type ClassroomListCoursesArgs struct {
	Account string `json:"account,omitempty"`
	Limit   int    `json:"limit,omitempty"`
}

// ClassroomListAssignmentsArgs represents arguments for classroom_list_assignments.
type ClassroomListAssignmentsArgs struct {
	Account  string `json:"account,omitempty"`
	CourseID string `json:"course_id"`
	Limit    int    `json:"limit,omitempty"`
}

// ClassroomGetAssignmentArgs represents arguments for classroom_get_assignment.
type ClassroomGetAssignmentArgs struct {
	Account      string `json:"account,omitempty"`
	CourseID     string `json:"course_id"`
	AssignmentID string `json:"assignment_id"`
}

// ClassroomListAnnouncementsArgs represents arguments for classroom_list_announcements.
type ClassroomListAnnouncementsArgs struct {
	Account  string `json:"account,omitempty"`
	CourseID string `json:"course_id"`
	Limit    int    `json:"limit,omitempty"`
}

// ClassroomCourseItem represents a Google Classroom course summary.
type ClassroomCourseItem struct {
	ID            string `json:"id"`
	Name          string `json:"name"`
	Section       string `json:"section,omitempty"`
	Description   string `json:"description,omitempty"`
	AlternateLink string `json:"alternate_link,omitempty"`
}

// ClassroomAssignmentItem represents coursework assignment details.
type ClassroomAssignmentItem struct {
	ID            string   `json:"id"`
	Title         string   `json:"title"`
	Description   string   `json:"description,omitempty"`
	AlternateLink string   `json:"alternate_link,omitempty"`
	DueDate       string   `json:"due_date,omitempty"`
	MaxPoints     *float64 `json:"max_points,omitempty"`
	State         string   `json:"state,omitempty"`
}

// ClassroomAnnouncementItem represents a post or announcement in a course.
type ClassroomAnnouncementItem struct {
	ID            string `json:"id"`
	Text          string `json:"text"`
	AlternateLink string `json:"alternate_link,omitempty"`
	CreationTime  string `json:"creation_time,omitempty"`
}

type classroomDueDate struct {
	Year  int `json:"year"`
	Month int `json:"month"`
	Day   int `json:"day"`
}

type classroomDueTime struct {
	Hours   int `json:"hours"`
	Minutes int `json:"minutes"`
}

func formatClassroomDue(d classroomDueDate, t classroomDueTime) string {
	if d.Year == 0 || d.Month == 0 || d.Day == 0 {
		return ""
	}
	if t.Hours == 0 && t.Minutes == 0 {
		return fmt.Sprintf("%04d-%02d-%02d", d.Year, d.Month, d.Day)
	}
	return fmt.Sprintf("%04d-%02d-%02d %02d:%02d", d.Year, d.Month, d.Day, t.Hours, t.Minutes)
}

func clampClassroomLimit(limit int) int {
	if limit <= 0 {
		return defaultClassroomPageLimit
	}
	if limit > maxClassroomPageLimit {
		return maxClassroomPageLimit
	}
	return limit
}

// ClassroomListCoursesTool lists active Google Classroom courses for an account.
type ClassroomListCoursesTool struct {
	client *GoogleClient
}

func NewClassroomListCoursesTool(client *GoogleClient) *ClassroomListCoursesTool {
	return &ClassroomListCoursesTool{client: client}
}

func (t *ClassroomListCoursesTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "classroom_list_courses",
		Category:    "workspace",
		Description: "Lists active Google Classroom courses that the user is enrolled in or teaching.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Complete email address of the account (e.g. 'user@example.com', 'work@company.com')"},
				"limit": {"type": "integer", "description": "Maximum courses to retrieve (default: 20, max: 100)"}
			}
		}`,
		PromptUsageTip:     "Use classroom_list_courses to find active course names and course IDs for coursework lookups.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *ClassroomListCoursesTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args ClassroomListCoursesArgs
	if argsJSON != "" {
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
		}
	}

	limit := clampClassroomLimit(args.Limit)
	endpoint := fmt.Sprintf("%s/courses?courseStates=ACTIVE&pageSize=%d", classroomAPIBaseURL, limit)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to query Classroom API: %v", err)}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Classroom API error (%d): %s", resp.StatusCode, string(body))}, nil
	}

	var data struct {
		Courses []struct {
			ID                 string `json:"id"`
			Name               string `json:"name"`
			Section            string `json:"section"`
			DescriptionHeading string `json:"descriptionHeading"`
			AlternateLink      string `json:"alternateLink"`
		} `json:"courses"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to decode courses response: %v", err)}, nil
	}

	courses := make([]ClassroomCourseItem, 0, len(data.Courses))
	for _, c := range data.Courses {
		courses = append(courses, ClassroomCourseItem{
			ID:            c.ID,
			Name:          c.Name,
			Section:       c.Section,
			Description:   c.DescriptionHeading,
			AlternateLink: c.AlternateLink,
		})
	}

	outJSON, _ := json.MarshalIndent(courses, "", "  ")
	return &tools.ToolResult{Stdout: string(outJSON)}, nil
}

// ClassroomListAssignmentsTool lists coursework items for a course.
type ClassroomListAssignmentsTool struct {
	client *GoogleClient
}

func NewClassroomListAssignmentsTool(client *GoogleClient) *ClassroomListAssignmentsTool {
	return &ClassroomListAssignmentsTool{client: client}
}

func (t *ClassroomListAssignmentsTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "classroom_list_assignments",
		Category:    "workspace",
		Description: "Lists coursework assignments, due dates, and point values for a specified Google Classroom course.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Complete email address of the account (e.g. 'user@example.com', 'work@company.com')"},
				"course_id": {"type": "string", "description": "Google Classroom course ID"},
				"limit": {"type": "integer", "description": "Maximum assignments to return (default: 20, max: 100)"}
			},
			"required": ["course_id"]
		}`,
		PromptUsageTip:     "Use classroom_list_assignments to inspect upcoming homework, projects, and due dates for a course.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *ClassroomListAssignmentsTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args ClassroomListAssignmentsArgs
	if argsJSON != "" {
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
		}
	}

	courseID := strings.TrimSpace(args.CourseID)
	if courseID == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "missing required argument: course_id"}, nil
	}

	limit := clampClassroomLimit(args.Limit)
	endpoint := fmt.Sprintf("%s/courses/%s/courseWork?pageSize=%d", classroomAPIBaseURL, url.PathEscape(courseID), limit)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to query Classroom API: %v", err)}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Classroom API error (%d): %s", resp.StatusCode, string(body))}, nil
	}

	var data struct {
		CourseWork []struct {
			ID            string           `json:"id"`
			Title         string           `json:"title"`
			Description   string           `json:"description"`
			AlternateLink string           `json:"alternateLink"`
			DueDate       classroomDueDate `json:"dueDate"`
			DueTime       classroomDueTime `json:"dueTime"`
			MaxPoints     *float64         `json:"maxPoints"`
			State         string           `json:"state"`
		} `json:"courseWork"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to decode coursework response: %v", err)}, nil
	}

	assignments := make([]ClassroomAssignmentItem, 0, len(data.CourseWork))
	for _, cw := range data.CourseWork {
		assignments = append(assignments, ClassroomAssignmentItem{
			ID:            cw.ID,
			Title:         cw.Title,
			Description:   cw.Description,
			AlternateLink: cw.AlternateLink,
			DueDate:       formatClassroomDue(cw.DueDate, cw.DueTime),
			MaxPoints:     cw.MaxPoints,
			State:         cw.State,
		})
	}

	outJSON, _ := json.MarshalIndent(assignments, "", "  ")
	return &tools.ToolResult{Stdout: string(outJSON)}, nil
}

// ClassroomGetAssignmentTool retrieves detailed information for a single assignment.
type ClassroomGetAssignmentTool struct {
	client *GoogleClient
}

func NewClassroomGetAssignmentTool(client *GoogleClient) *ClassroomGetAssignmentTool {
	return &ClassroomGetAssignmentTool{client: client}
}

func (t *ClassroomGetAssignmentTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "classroom_get_assignment",
		Category:    "workspace",
		Description: "Retrieves complete details, description, due date, and points for a specific Google Classroom assignment.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Complete email address of the account (e.g. 'user@example.com', 'work@company.com')"},
				"course_id": {"type": "string", "description": "Google Classroom course ID"},
				"assignment_id": {"type": "string", "description": "Coursework assignment ID"}
			},
			"required": ["course_id", "assignment_id"]
		}`,
		PromptUsageTip:     "Use classroom_get_assignment after obtaining assignment IDs from classroom_list_assignments to inspect complete instructions.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *ClassroomGetAssignmentTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args ClassroomGetAssignmentArgs
	if argsJSON != "" {
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
		}
	}

	courseID := strings.TrimSpace(args.CourseID)
	assignmentID := strings.TrimSpace(args.AssignmentID)
	if courseID == "" || assignmentID == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "missing required arguments: course_id and assignment_id"}, nil
	}

	endpoint := fmt.Sprintf("%s/courses/%s/courseWork/%s",
		classroomAPIBaseURL,
		url.PathEscape(courseID),
		url.PathEscape(assignmentID),
	)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to query Classroom API: %v", err)}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Classroom API error (%d): %s", resp.StatusCode, string(body))}, nil
	}

	var cw struct {
		ID            string           `json:"id"`
		Title         string           `json:"title"`
		Description   string           `json:"description"`
		AlternateLink string           `json:"alternateLink"`
		DueDate       classroomDueDate `json:"dueDate"`
		DueTime       classroomDueTime `json:"dueTime"`
		MaxPoints     *float64         `json:"maxPoints"`
		State         string           `json:"state"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&cw); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to decode assignment response: %v", err)}, nil
	}

	item := ClassroomAssignmentItem{
		ID:            cw.ID,
		Title:         cw.Title,
		Description:   cw.Description,
		AlternateLink: cw.AlternateLink,
		DueDate:       formatClassroomDue(cw.DueDate, cw.DueTime),
		MaxPoints:     cw.MaxPoints,
		State:         cw.State,
	}

	outJSON, _ := json.MarshalIndent(item, "", "  ")
	return &tools.ToolResult{Stdout: string(outJSON)}, nil
}

// ClassroomListAnnouncementsTool retrieves stream posts and announcements for a course.
type ClassroomListAnnouncementsTool struct {
	client *GoogleClient
}

func NewClassroomListAnnouncementsTool(client *GoogleClient) *ClassroomListAnnouncementsTool {
	return &ClassroomListAnnouncementsTool{client: client}
}

func (t *ClassroomListAnnouncementsTool) Metadata() tools.ToolMetadata {
	return tools.ToolMetadata{
		Name:        "classroom_list_announcements",
		Category:    "workspace",
		Description: "Lists teacher announcements, stream notices, and updates for a Google Classroom course.",
		ParameterSchema: `{
			"type": "object",
			"properties": {
				"account": {"type": "string", "description": "Complete email address of the account (e.g. 'user@example.com', 'work@company.com')"},
				"course_id": {"type": "string", "description": "Google Classroom course ID"},
				"limit": {"type": "integer", "description": "Maximum announcements to retrieve (default: 20, max: 100)"}
			},
			"required": ["course_id"]
		}`,
		PromptUsageTip:     "Use classroom_list_announcements to check instructor updates, room changes, and class news.",
		Risk:               tools.RiskLow,
		RequiredCapability: "workspace:read",
	}
}

func (t *ClassroomListAnnouncementsTool) Execute(ctx context.Context, argsJSON string) (*tools.ToolResult, error) {
	var args ClassroomListAnnouncementsArgs
	if argsJSON != "" {
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("invalid arguments: %v", err)}, nil
		}
	}

	courseID := strings.TrimSpace(args.CourseID)
	if courseID == "" {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: "missing required argument: course_id"}, nil
	}

	limit := clampClassroomLimit(args.Limit)
	endpoint := fmt.Sprintf("%s/courses/%s/announcements?pageSize=%d",
		classroomAPIBaseURL,
		url.PathEscape(courseID),
		limit,
	)

	resp, err := t.client.DoAuthorizedRequest(ctx, args.Account, http.MethodGet, endpoint, nil)
	if err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to query Classroom API: %v", err)}, nil
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("Classroom API error (%d): %s", resp.StatusCode, string(body))}, nil
	}

	var data struct {
		Announcements []struct {
			ID            string `json:"id"`
			Text          string `json:"text"`
			AlternateLink string `json:"alternateLink"`
			CreationTime  string `json:"creationTime"`
		} `json:"announcements"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return &tools.ToolResult{IsError: true, ExitCode: 1, Stderr: fmt.Sprintf("failed to decode announcements response: %v", err)}, nil
	}

	announcements := make([]ClassroomAnnouncementItem, 0, len(data.Announcements))
	for _, a := range data.Announcements {
		announcements = append(announcements, ClassroomAnnouncementItem{
			ID:            a.ID,
			Text:          a.Text,
			AlternateLink: a.AlternateLink,
			CreationTime:  a.CreationTime,
		})
	}

	outJSON, _ := json.MarshalIndent(announcements, "", "  ")
	return &tools.ToolResult{Stdout: string(outJSON)}, nil
}
