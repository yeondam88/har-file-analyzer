'use client';

import React, { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { uploadHARFile, testCorsConnection } from '@/lib/api/har-files';
import { toast } from 'sonner';

interface FileUploaderProps {
  onUploadSuccess: (fileId: string) => void;
}

export default function FileUploader({ onUploadSuccess }: FileUploaderProps) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [testing, setTesting] = useState(false);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'application/json': ['.har'],
    },
    maxFiles: 1,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setFile(acceptedFiles[0]);
      }
    },
  });

  const uploadFile = async () => {
    if (!file) {
      toast.error('Please select a HAR file to upload');
      return;
    }

    setUploading(true);
    setProgress(0);

    // Simulate progress - in a real app, you'd get this from the API if it supports it
    const progressInterval = setInterval(() => {
      setProgress((prev) => Math.min(prev + 10, 90));
    }, 300);

    try {
      const response = await uploadHARFile(file, description);
      setProgress(100);
      clearInterval(progressInterval);
      toast.success(`File ${file.name} uploaded successfully!`);
      
      // Notify parent component
      onUploadSuccess(response.id);
      
      // Reset form
      setFile(null);
      setDescription('');
    } catch (error) {
      console.error('Error uploading file:', error);
      toast.error('Failed to upload file. Please try again.');
    } finally {
      clearInterval(progressInterval);
      setUploading(false);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      const result = await testCorsConnection();
      toast.success(`CORS test successful: ${result.message || 'Connection established'}`);
    } catch (error) {
      console.error('CORS test failed:', error);
      toast.error('CORS test failed. Check console for details.');
    } finally {
      setTesting(false);
    }
  };

  return (
    <Card className="w-full">
      <CardContent className="pt-6">
        <div 
          {...getRootProps()} 
          className={`border-2 border-dashed rounded-lg p-6 mb-4 text-center cursor-pointer transition-colors ${
            isDragActive ? 'border-primary bg-primary/10' : 'border-muted-foreground/20'
          }`}
        >
          <input {...getInputProps()} />
          {file ? (
            <div className="space-y-2">
              <p className="text-sm font-medium">Selected file:</p>
              <p className="text-base">{file.name}</p>
              <p className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-base font-medium">
                {isDragActive ? 'Drop the HAR file here' : 'Drag & drop your HAR file here'}
              </p>
              <p className="text-sm text-muted-foreground">or click to select a file</p>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <Input
              placeholder="Description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={uploading}
              className="w-full"
            />
          </div>

          {uploading && (
            <div className="space-y-2">
              <Progress value={progress} className="w-full h-2" />
              <p className="text-xs text-center text-muted-foreground">{progress}% Uploaded</p>
            </div>
          )}

          <Button
            onClick={uploadFile}
            disabled={!file || uploading}
            className="w-full"
          >
            {uploading ? 'Uploading...' : 'Upload HAR File'}
          </Button>
          
          <div className="flex justify-center pt-2">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={testConnection} 
              disabled={testing}
            >
              {testing ? 'Testing...' : 'Test CORS Connection'}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
} 