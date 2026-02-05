"use client";

import { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from "react";
import { Send, Loader2, Zap, Paperclip, X, FileText, CheckCircle2, AlertCircle, Trash2, RefreshCw } from "lucide-react";
import { uploadFiles as uploadFilesApi, createThread, deleteFile as deleteFileApi, getFileProcessingStatus, MessageAttachment } from "@/lib/api";

interface SelectedFile {
  file: File;
  status: "pending" | "uploading" | "processing" | "ready" | "error" | "deleting";
  progress: number;
  error?: string;
  s3_key?: string;  // Stored after successful upload
}

interface InputAreaProps {
  onSend: (message: string, attachments?: MessageAttachment[]) => void;
  isLoading: boolean;
  disabled?: boolean;
  userId: string;
  threadId: string | null;
  onThreadCreated?: (threadId: string) => void;
}

const ALLOWED_EXTENSIONS = [".pdf", ".pptx"];
const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB

export function InputArea({ 
  onSend, 
  isLoading, 
  disabled, 
  userId, 
  threadId,
  onThreadCreated 
}: InputAreaProps) {
  const [input, setInput] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [overallProgress, setOverallProgress] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingIntervalsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Clear selected files when thread changes
  useEffect(() => {
    setSelectedFiles([]);
    setIsUploading(false);
    setOverallProgress(0);
    // Clear all polling intervals
    pollingIntervalsRef.current.forEach((interval) => clearInterval(interval));
    pollingIntervalsRef.current.clear();
  }, [threadId]);

  // Cleanup polling intervals on unmount
  useEffect(() => {
    return () => {
      pollingIntervalsRef.current.forEach((interval) => clearInterval(interval));
      pollingIntervalsRef.current.clear();
    };
  }, []);

  // Start polling for file processing status
  const startProcessingPoll = (filename: string, currentThreadId: string) => {
    // Don't start if already polling this file
    if (pollingIntervalsRef.current.has(filename)) {
      console.log(`[Poll] Already polling ${filename}`);
      return;
    }

    console.log(`[Poll] Starting polling for ${filename} in thread ${currentThreadId}`);

    const pollStatus = async () => {
      try {
        console.log(`[Poll] Checking status for ${filename}...`);
        const status = await getFileProcessingStatus(userId, currentThreadId, filename);
        console.log(`[Poll] Status for ${filename}:`, status);
        
        if (status.processed) {
          console.log(`[Poll] ${filename} is ready! Chunks: ${status.chunk_count}`);
          // File is ready - update status and stop polling
          setSelectedFiles((prev) =>
            prev.map((f) =>
              f.file.name === filename && f.status === "processing"
                ? { ...f, status: "ready" }
                : f
            )
          );
          // Clear the polling interval
          const interval = pollingIntervalsRef.current.get(filename);
          if (interval) {
            clearInterval(interval);
            pollingIntervalsRef.current.delete(filename);
          }
        }
      } catch (error) {
        console.error(`[Poll] Failed to poll status for ${filename}:`, error);
      }
    };

    // Poll immediately, then every 2 seconds
    pollStatus();
    const interval = setInterval(pollStatus, 2000);
    pollingIntervalsRef.current.set(filename, interval);
  };

  const validateFile = (file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Invalid file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Max size: ${MAX_FILE_SIZE / 1024 / 1024}MB`;
    }
    return null;
  };

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newFiles: SelectedFile[] = [];
    const validFiles: File[] = [];
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const error = validateFile(file);
      if (error) {
        newFiles.push({
          file,
          status: "error",
          progress: 0,
          error,
        });
      } else {
        newFiles.push({
          file,
          status: "pending",
          progress: 0,
        });
        validFiles.push(file);
      }
    }

    setSelectedFiles((prev) => [...prev, ...newFiles]);
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    // Auto-upload valid files
    if (validFiles.length > 0) {
      await uploadFilesAuto(validFiles);
    }
  };

  const uploadFilesAuto = async (filesToUpload: File[]) => {
    if (filesToUpload.length === 0) return;

    // Ensure we have a thread ID
    let currentThreadId = threadId;
    if (!currentThreadId) {
      try {
        const newThread = await createThread(userId);
        currentThreadId = newThread.id;
        onThreadCreated?.(currentThreadId);
      } catch (error) {
        console.error("Failed to create thread for file upload:", error);
        setSelectedFiles((prev) =>
          prev.map((f) =>
            f.status === "pending"
              ? { ...f, status: "error", error: "Failed to create thread" }
              : f
          )
        );
        return;
      }
    }

    setIsUploading(true);
    setOverallProgress(0);

    // Update status to uploading for the files we're about to upload
    const fileNames = new Set(filesToUpload.map(f => f.name));
    setSelectedFiles((prev) =>
      prev.map((f) =>
        f.status === "pending" && fileNames.has(f.file.name) 
          ? { ...f, status: "uploading" } 
          : f
      )
    );

    try {
      const result = await uploadFilesApi(
        filesToUpload,
        userId,
        currentThreadId,
        (progress) => {
          setOverallProgress(progress);
        }
      );

      // Determine which files uploaded successfully and need polling
      const filesToPoll: string[] = [];
      
      // Process results - identify successful uploads
      for (const uploadResult of result.uploaded) {
        if (!uploadResult.error && uploadResult.key) {
          filesToPoll.push(uploadResult.filename);
        }
      }

      // Update file statuses based on result
      setSelectedFiles((prev) =>
        prev.map((f) => {
          if (f.status !== "uploading") return f;
          
          const uploadResult = result.uploaded.find(
            (r) => r.filename === f.file.name
          );
          
          if (uploadResult?.error) {
            return { ...f, status: "error", error: uploadResult.error, progress: 100 };
          }
          // Mark as processing
          return { 
            ...f, 
            status: "processing", 
            progress: 100,
            s3_key: uploadResult?.key,  // Store the S3 key for attachments
          };
        })
      );
      
      // Start polling for processing status (after state update)
      if (currentThreadId && filesToPoll.length > 0) {
        // Use setTimeout to ensure state update has been applied
        setTimeout(() => {
          filesToPoll.forEach((filename) => {
            startProcessingPoll(filename, currentThreadId);
          });
        }, 100);
      }
    } catch (error) {
      console.error("Upload failed:", error);
      setSelectedFiles((prev) =>
        prev.map((f) =>
          f.status === "uploading"
            ? { ...f, status: "error", error: "Upload failed", progress: 0 }
            : f
        )
      );
    } finally {
      setIsUploading(false);
    }
  };

  const removeFile = async (index: number) => {
    const fileToRemove = selectedFiles[index];
    
    // Clear any polling for this file
    const interval = pollingIntervalsRef.current.get(fileToRemove.file.name);
    if (interval) {
      clearInterval(interval);
      pollingIntervalsRef.current.delete(fileToRemove.file.name);
    }
    
    // If file was successfully processed, delete from S3
    if (fileToRemove.status === "ready" && threadId) {
      // Update status to deleting
      setSelectedFiles((prev) =>
        prev.map((f, i) => (i === index ? { ...f, status: "deleting" } : f))
      );
      
      try {
        await deleteFileApi(userId, threadId, fileToRemove.file.name);
        // Remove from list after successful deletion
        setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
      } catch (error) {
        console.error("Failed to delete file from S3:", error);
        const errorMessage = error instanceof Error ? error.message : "Failed to delete";
        // Revert status and show error
        setSelectedFiles((prev) =>
          prev.map((f, i) =>
            i === index ? { ...f, status: "error", error: errorMessage } : f
          )
        );
      }
    } else {
      // Just remove from list if not uploaded yet or no thread
      setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    }
  };

  // Check if any files are not ready yet (pending, uploading, or processing)
  const hasUnreadyFiles = selectedFiles.some(
    f => f.status === "pending" || f.status === "uploading" || f.status === "processing"
  );

  const handleSubmit = () => {
    if (input.trim() && !isLoading && !disabled && !hasUnreadyFiles) {
      // Collect ready files as attachments
      const attachments: MessageAttachment[] = selectedFiles
        .filter(f => f.status === "ready")
        .map(f => ({
          filename: f.file.name,
          size: f.file.size,
          s3_key: f.s3_key,
          content_type: f.file.type || undefined,
        }));
      
      onSend(input.trim(), attachments.length > 0 ? attachments : undefined);
      setInput("");
      
      // Clear ready files after sending and stop their polling
      const readyFiles = selectedFiles.filter(f => f.status === "ready");
      readyFiles.forEach(f => {
        const interval = pollingIntervalsRef.current.get(f.file.name);
        if (interval) {
          clearInterval(interval);
          pollingIntervalsRef.current.delete(f.file.name);
        }
      });
      setSelectedFiles(prev => prev.filter(f => f.status !== "ready"));
      
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const hasFiles = selectedFiles.length > 0;

  // Circular progress component
  const CircularProgress = ({ progress }: { progress: number }) => {
    const radius = 8;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (progress / 100) * circumference;
    
    return (
      <svg className="w-5 h-5 -rotate-90" viewBox="0 0 20 20">
        {/* Background circle */}
        <circle
          cx="10"
          cy="10"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="text-surface-tertiary"
        />
        {/* Progress circle */}
        <circle
          cx="10"
          cy="10"
          r={radius}
          fill="none"
          stroke="url(#progressGradient)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-300"
        />
        <defs>
          <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#00fff2" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
        </defs>
      </svg>
    );
  };

  return (
    <div className="border-t border-neon-cyan/10 bg-surface-secondary/50 backdrop-blur-sm p-4">
      <div className="max-w-4xl mx-auto">
        {/* Selected Files Display */}
        {hasFiles && (
          <div className="mb-3 flex flex-wrap gap-2">
            {selectedFiles.map((sf, index) => (
              <div
                key={`${sf.file.name}-${index}`}
                className={`
                  flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                  ${sf.status === "error" 
                    ? "bg-red-500/10 border border-red-500/30" 
                    : sf.status === "ready"
                    ? "bg-green-500/10 border border-green-500/30"
                    : sf.status === "uploading"
                    ? "bg-neon-cyan/10 border border-neon-cyan/30"
                    : sf.status === "processing"
                    ? "bg-amber-500/10 border border-amber-500/30"
                    : sf.status === "deleting"
                    ? "bg-red-500/5 border border-red-500/20 opacity-70"
                    : "bg-surface-tertiary border border-neon-cyan/20"
                  }
                `}
              >
                <FileText className="w-4 h-4 text-neon-cyan/60" />
                <span className="max-w-[150px] truncate text-text-secondary">
                  {sf.file.name}
                </span>
                
                {sf.status === "uploading" && (
                  <div className="flex items-center gap-1.5">
                    <CircularProgress progress={overallProgress} />
                    <span className="text-xs text-neon-cyan font-medium">{overallProgress}%</span>
                  </div>
                )}
                
                {sf.status === "processing" && (
                  <div className="flex items-center gap-1.5">
                    <RefreshCw className="w-4 h-4 animate-spin text-amber-500" />
                    <span className="text-xs text-amber-500 font-medium">Processing...</span>
                  </div>
                )}
                
                {sf.status === "deleting" && (
                  <div className="flex items-center gap-1.5">
                    <Loader2 className="w-4 h-4 animate-spin text-red-400" />
                    <span className="text-xs text-red-400">Deleting...</span>
                  </div>
                )}
                
                {sf.status === "ready" && (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                )}
                
                {sf.status === "error" && (
                  <div className="flex items-center gap-1" title={sf.error}>
                    <AlertCircle className="w-4 h-4 text-red-500" />
                  </div>
                )}
                
                {sf.status !== "deleting" && sf.status !== "uploading" && sf.status !== "processing" && (
                  <button
                    onClick={() => removeFile(index)}
                    className="ml-1 p-1 hover:bg-white/10 rounded transition-colors group"
                    title={sf.status === "ready" ? "Delete from S3" : "Remove"}
                  >
                    {sf.status === "ready" ? (
                      <Trash2 className="w-3.5 h-3.5 text-text-muted group-hover:text-red-400" />
                    ) : (
                      <X className="w-3 h-3 text-text-muted group-hover:text-text-primary" />
                    )}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="relative">
          {/* Glow effect behind input */}
          <div className="absolute inset-0 bg-gaming-gradient opacity-5 rounded-2xl blur-xl" />
          
          <div className="relative flex items-end gap-3 bg-surface-tertiary/80 rounded-2xl border border-neon-cyan/20 p-3 focus-within:border-neon-cyan/50 focus-within:shadow-inner-glow transition-all">
            {/* File Upload Button */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.pptx"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || isLoading || isUploading}
              className="flex-shrink-0 w-10 h-10 rounded-xl border border-neon-cyan/30 
                       hover:bg-neon-cyan/10 hover:border-neon-cyan/50 
                       disabled:opacity-30 disabled:cursor-not-allowed 
                       flex items-center justify-center transition-all"
              title="Upload PDF or PPTX files"
            >
              <Paperclip className="w-5 h-5 text-neon-cyan/70" />
            </button>

            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about games, strategies, lore..."
              disabled={disabled || isLoading}
              rows={1}
              className="flex-1 bg-transparent resize-none outline-none text-text-primary placeholder:text-text-muted min-h-[28px] max-h-[200px] text-base"
            />
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || isLoading || disabled || hasUnreadyFiles}
              className="flex-shrink-0 w-11 h-11 rounded-xl btn-gaming disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:transform-none disabled:hover:shadow-none flex items-center justify-center transition-all"
              title={hasUnreadyFiles ? "Wait for files to finish processing" : undefined}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
        </div>
        
        <div className="flex items-center justify-center gap-2 mt-3">
          <Zap className="w-3 h-3 text-neon-cyan/40" />
          <p className="text-xs text-text-muted">
            Powered by <span className="text-neon-cyan/60 font-display">SUPER CHAT</span> • Gaming-focused responses only
          </p>
        </div>
      </div>
    </div>
  );
}
