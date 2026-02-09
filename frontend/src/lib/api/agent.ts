import type { ChatRequest, ChatResponse, LoginResponse, User } from '../types/chat';
import { apiRequest } from './client';

export async function register(username: string, email: string, password: string): Promise<User> {
  return apiRequest<User>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      username,
      email,
      password,
    }),
  });
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({
      login: username,
      password,
    }),
  });
}

export async function getMe(): Promise<User> {
  return apiRequest<User>('/auth/me');
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  return apiRequest<ChatResponse>('/agent/chat', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}
