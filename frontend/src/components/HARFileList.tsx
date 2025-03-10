'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { getHARFiles, deleteHARFile, exportMarkdown, exportPostman, generateReport, HARFileWithCount } from '@/lib/api/har-files';
import { downloadBlob, formatFileSize } from '@/lib/utils';
import { toast } from 'sonner';

export default function HARFileList() {
  const [files, setFiles] = useState<HARFileWithCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFile, setSelectedFile] = useState<HARFileWithCount | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Fetch the list of HAR files
  const fetchFiles = async () => {
    setLoading(true);
    try {
      const data = await getHARFiles();
      setFiles(data);
    } catch (error) {
      console.error('Error fetching HAR files:', error);
      toast.error('Failed to load HAR files');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  // Delete a HAR file
  const handleDelete = async (id: string) => {
    try {
      await deleteHARFile(id);
      toast.success('File deleted successfully');
      fetchFiles(); // Refresh the list
    } catch (error) {
      console.error('Error deleting file:', error);
      toast.error('Failed to delete file');
    }
  };

  // Generate and download a report
  const handleGenerateReport = async (
    fileId: string, 
    reportType: 'general' | 'auth' | 'endpoints' | 'enhanced-patterns' | 'similar-apis',
    format: 'json' | 'markdown' = 'markdown',
    download: boolean = true
  ) => {
    try {
      const file = files.find(f => f.id === fileId);
      if (!file) return;
      
      toast.info(`Generating ${reportType} report...`);
      
      const data = await generateReport(fileId, reportType, format, download);
      
      if (format === 'markdown' && download) {
        const filename = `${file.filename.split('.')[0]}_${reportType.replace('-', '_')}.md`;
        downloadBlob(data, filename);
        toast.success(`Report downloaded as ${filename}`);
      } else {
        // Handle JSON data if needed
        console.log('Report data:', data);
        toast.success('Report generated successfully');
      }
    } catch (error) {
      console.error('Error generating report:', error);
      toast.error('Failed to generate report');
    }
  };

  // Export as Markdown documentation
  const handleExportMarkdown = async (fileId: string) => {
    try {
      const file = files.find(f => f.id === fileId);
      if (!file) return;
      
      toast.info('Generating Markdown documentation...');
      
      const data = await exportMarkdown(fileId);
      const filename = `${file.filename.split('.')[0]}_api_docs.md`;
      downloadBlob(data, filename);
      
      toast.success(`Documentation downloaded as ${filename}`);
    } catch (error) {
      console.error('Error exporting markdown:', error);
      toast.error('Failed to export markdown documentation');
    }
  };

  // Export as Postman collection
  const handleExportPostman = async (fileId: string) => {
    try {
      const file = files.find(f => f.id === fileId);
      if (!file) return;
      
      toast.info('Generating Postman collection...');
      
      const data = await exportPostman(fileId);
      const filename = `${file.filename.split('.')[0]}_postman_collection.json`;
      downloadBlob(data, filename);
      
      toast.success(`Postman collection downloaded as ${filename}`);
    } catch (error) {
      console.error('Error exporting Postman collection:', error);
      toast.error('Failed to export Postman collection');
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Your HAR Files</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-center py-4">Loading...</p>
          ) : files.length === 0 ? (
            <p className="text-center py-4">No HAR files found. Upload your first file to get started.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Filename</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>API Calls</TableHead>
                  <TableHead>Browser</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {files.map((file) => (
                  <TableRow key={file.id}>
                    <TableCell className="font-medium">{file.filename}</TableCell>
                    <TableCell>{formatFileSize(file.file_size)}</TableCell>
                    <TableCell>{file.api_call_count}</TableCell>
                    <TableCell>{file.browser || 'Unknown'}</TableCell>
                    <TableCell>{new Date(file.created_at).toLocaleDateString()}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end space-x-2">
                        <Dialog open={dialogOpen && selectedFile?.id === file.id} onOpenChange={(open) => {
                          setDialogOpen(open);
                          if (!open) setSelectedFile(null);
                        }}>
                          <DialogTrigger asChild>
                            <Button 
                              variant="outline" 
                              onClick={() => {
                                setSelectedFile(file);
                                setDialogOpen(true);
                              }}
                            >
                              Details
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="sm:max-w-[500px]">
                            <DialogHeader>
                              <DialogTitle>{file.filename}</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                              <div className="grid grid-cols-2 gap-2">
                                <div className="font-medium">File Size:</div>
                                <div>{formatFileSize(file.file_size)}</div>
                                
                                <div className="font-medium">API Calls:</div>
                                <div>{file.api_call_count}</div>
                                
                                <div className="font-medium">Browser:</div>
                                <div>{file.browser || 'Unknown'}</div>
                                
                                <div className="font-medium">Uploaded:</div>
                                <div>{new Date(file.created_at).toLocaleString()}</div>
                                
                                {file.description && (
                                  <>
                                    <div className="font-medium">Description:</div>
                                    <div>{file.description}</div>
                                  </>
                                )}
                              </div>
                            </div>
                          </DialogContent>
                        </Dialog>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="outline">Generate Report</Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent>
                            <DropdownMenuItem onClick={() => handleGenerateReport(file.id, 'general')}>
                              General Analysis
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleGenerateReport(file.id, 'auth')}>
                              Authentication Analysis
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleGenerateReport(file.id, 'endpoints')}>
                              Endpoints Analysis
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleGenerateReport(file.id, 'enhanced-patterns')}>
                              Enhanced Patterns
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleGenerateReport(file.id, 'similar-apis')}>
                              Similar APIs
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>

                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="outline">Export</Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent>
                            <DropdownMenuItem onClick={() => handleExportMarkdown(file.id)}>
                              Export as Markdown
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleExportPostman(file.id)}>
                              Export as Postman Collection
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>

                        <Button 
                          variant="destructive" 
                          onClick={() => handleDelete(file.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
} 