-- Migration: Add email field to users table
-- Created: 2026-01-19
-- Description: Adds email column with unique constraint to support email-based user lookup

-- Add email column to users table (nullable to not break existing records)
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS email TEXT;

-- Add unique constraint on email (only for non-null values)
-- This allows multiple NULL values but ensures email uniqueness when provided
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key 
ON public.users(email) 
WHERE email IS NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN public.users.email IS 'User email address for identification and communication';

-- Verification query (uncomment to test after migration)
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'users' AND table_schema = 'public';
