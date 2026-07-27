export interface Course {
  id: number;
  user_id: number;
  code: string;
  title: string;
  total_marks: number;
  grading_scale: Record<string, unknown>;
  language: string;
}

export interface MarkingScheme {
  id: number;
  course_id: number;
  version: number;
  content: string;
  special_instructions: string | null;
  selection_rule: string | null;
}
