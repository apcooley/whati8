<script lang="ts">
  import type { Message } from '../types/chat';

  export let message: Message;

  function formatTime(date: Date): string {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
  }

  function formatDateTime(date: Date): string {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
    });
  }
</script>

<div class={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} mb-4`}>
  <div
    class={`max-w-[80%] rounded-lg px-4 py-2 ${
      message.role === 'user'
        ? 'bg-primary-600 text-white'
        : 'bg-white text-gray-900 border border-gray-200'
    }`}
  >
    <div class="whitespace-pre-wrap break-words">{message.content}</div>
    <div
      class={`text-xs mt-1 ${
        message.role === 'user' ? 'text-primary-100' : 'text-gray-500'
      }`}
    >
      {formatTime(message.timestamp)}
    </div>
  </div>
</div>
