/// <reference types="vite/client" />

interface Window {
  huggingface?: {
    variables?: Record<string, string | undefined>;
  };
}
