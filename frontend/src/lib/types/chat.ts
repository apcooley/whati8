export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  toolResults?: ToolResult[];
}

export interface ToolResult {
  tool: string;
  input: Record<string, any>;
  result: Record<string, any>;
}

export interface ChatRequest {
  message: string;
  session_id: string;
  conversation_history?: Message[];
}

export interface ChatResponse {
  message: string;
  session_id: string;
  timestamp: string;
  requires_form: boolean;
  form_data?: FormData;
  tool_results?: ToolResult[];
}

export interface FormData {
  form_type: 'food_selection' | 'log_confirmation';
  data: Record<string, any>;
}

export interface User {
  id: number;
  username: string;
  email: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}
