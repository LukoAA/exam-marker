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

export interface Batch {
  id: number;
  course_id: number;
  scheme_id: number;
  name: string;
  status: string;
}

export interface Script {
  id: number;
  batch_id: number;
  original_filename: string;
  page_count: number | null;
  student_name: string | null;
  matric_number: string | null;
  status: string;
  total_awarded: number | null;
  percentage: number | null;
  grade: string | null;
  needs_human_review: boolean;
}

export interface BatchDetail extends Batch {
  scripts: Script[];
}
