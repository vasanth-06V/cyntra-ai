export type Resume = {
  id: string;
  file_key: string;
  parsed_text: string | null;
  /** Optional name chosen by the owner (1-80 chars); the file name is shown when null. */
  display_name?: string | null;
  created_at: string;
};
