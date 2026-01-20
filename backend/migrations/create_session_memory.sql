-- Create session_memory table to track active sessions
CREATE TABLE IF NOT EXISTS public.session_memory (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id text NOT NULL UNIQUE,
  user_id uuid NULL,
  started_at timestamp with time zone NULL DEFAULT now(),
  last_activity_at timestamp with time zone NULL DEFAULT now(),
  metadata jsonb NULL DEFAULT '{}'::jsonb,
  CONSTRAINT session_memory_pkey PRIMARY KEY (id),
  CONSTRAINT session_memory_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_session_memory_session_id ON public.session_memory(session_id);
CREATE INDEX IF NOT EXISTS idx_session_memory_user_id ON public.session_memory(user_id);

-- Add comment
COMMENT ON TABLE public.session_memory IS 'Tracks active voice agent sessions and their associated users';
COMMENT ON COLUMN public.session_memory.session_id IS 'Unique identifier for the LiveKit session/room';
COMMENT ON COLUMN public.session_memory.user_id IS 'User ID once identified in the session (null if not yet identified)';
COMMENT ON COLUMN public.session_memory.metadata IS 'Additional session context (optional)';
