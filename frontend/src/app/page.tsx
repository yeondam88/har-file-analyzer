'use client';

import { useState } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import FileUploader from '@/components/FileUploader';
import HARFileList from '@/components/HARFileList';
import { Toaster } from '@/components/ui/sonner';

export default function Home() {
  const [activeTab, setActiveTab] = useState('files');
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUploadSuccess = () => {
    setActiveTab('files');
    setRefreshTrigger(prev => prev + 1);
  };

  return (
    <main className="min-h-screen p-6 md:p-10 bg-muted/20">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="space-y-2">
          <h1 className="text-3xl md:text-4xl font-bold">HAR File Analyzer</h1>
          <p className="text-muted-foreground">Upload, analyze and export HAR files to understand API patterns</p>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full md:w-[400px] grid-cols-2">
            <TabsTrigger value="files">Your HAR Files</TabsTrigger>
            <TabsTrigger value="upload">Upload New File</TabsTrigger>
          </TabsList>
          
          <TabsContent value="files" className="mt-6">
            <HARFileList key={refreshTrigger} />
          </TabsContent>
          
          <TabsContent value="upload" className="mt-6">
            <div className="grid md:grid-cols-2 gap-6">
              <Card className="md:col-span-1">
                <CardHeader>
                  <CardTitle>Upload HAR File</CardTitle>
                  <CardDescription>
                    Upload a HAR file to analyze API endpoints, authentication, and patterns
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FileUploader onUploadSuccess={handleUploadSuccess} />
                </CardContent>
              </Card>
              
              <Card className="md:col-span-1">
                <CardHeader>
                  <CardTitle>What is a HAR file?</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p>
                    A HAR (HTTP Archive) file is a JSON-formatted archive file that contains a record of all the HTTP requests and responses that a browser makes when loading a page.
                  </p>
                  <p>
                    You can generate a HAR file from your browser's developer tools:
                  </p>
                  <ul className="list-disc list-inside space-y-2">
                    <li>
                      <strong>Chrome/Edge:</strong> Open DevTools (F12) → Network tab → Record → Refresh page → Right-click → "Save all as HAR"
                    </li>
                    <li>
                      <strong>Firefox:</strong> Open DevTools (F12) → Network tab → Record → Refresh page → Right-click → "Save All As HAR"
                    </li>
                    <li>
                      <strong>Safari:</strong> Open Web Inspector → Network tab → Record → Refresh page → Export → Export HAR
                    </li>
                  </ul>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
      <Toaster />
    </main>
  );
}
