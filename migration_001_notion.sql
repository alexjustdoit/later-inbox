-- Migration 001: Add Notion sync support
-- Run this in your Supabase SQL editor

ALTER TABLE public.user_preferences
ADD COLUMN IF NOT EXISTS notion_token TEXT,
ADD COLUMN IF NOT EXISTS notion_database_id TEXT,
ADD COLUMN IF NOT EXISTS notion_insights_page_id TEXT,
ADD COLUMN IF NOT EXISTS notion_parent_page_id TEXT,
ADD COLUMN IF NOT EXISTS notion_auto_sync BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS notion_last_synced_at TIMESTAMPTZ;
