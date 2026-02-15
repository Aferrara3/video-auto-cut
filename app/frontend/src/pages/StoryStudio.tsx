import React from 'react';
import { 
    Box, 
    Typography, 
    Stepper, 
    Step, 
    StepLabel, 
    Button, 
    Paper, 
    CircularProgress,
    TextField,
    List,
    ListItem,
    ListItemText,
    Divider,
    Alert,
    LinearProgress
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import MovieIcon from '@mui/icons-material/Movie';
import DescriptionIcon from '@mui/icons-material/Description';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import DownloadIcon from '@mui/icons-material/Download';
import { jobs } from '../api/client';
import { useMutation, useQuery } from '@tanstack/react-query';

const steps = ['Upload Interview', 'Review Transcript', 'Review Story Plan', 'Render'];

export default function StoryStudio() {
  const [activeStep, setActiveStep] = React.useState(0);
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [srtContent, setSrtContent] = React.useState<string>('');
  const [plan, setPlan] = React.useState<any[]>([]);
  const [finalVideoUrl, setFinalVideoUrl] = React.useState<string | null>(null);
  
  // Status Polling
  const { data: jobStatus, refetch } = useQuery({
      queryKey: ['jobStatus', jobId],
      queryFn: () => jobs.getStatus(jobId!),
      enabled: !!jobId,
      refetchInterval: (query) => {
          const data = query.state.data;
          if (!data) return 2000;
          if (['done', 'failed'].includes(data.status)) return false;
          // If we are in a waiting state (transcribed, planned), stop polling until action taken
          // But actually we want to poll to detect completion of background tasks
          return 2000;
      },
  });

  // Watch status changes to auto-update local state
  React.useEffect(() => {
      if (!jobStatus) return;

      if (jobStatus.status === 'transcribed' && !srtContent) {
          setSrtContent(jobStatus.srt_content || '');
          if (activeStep === 0) setActiveStep(1); 
      }
      else if (jobStatus.status === 'planned') {
          setPlan(jobStatus.plan || []);
          if (activeStep === 1) setActiveStep(2);
      }
      else if (jobStatus.status === 'done') {
          setFinalVideoUrl(jobStatus.final_video_url);
          if (activeStep === 2) setActiveStep(3);
      }
  }, [jobStatus, activeStep, srtContent, plan, finalVideoUrl]);

  // Mutations
  const uploadMutation = useMutation({
      mutationFn: jobs.upload,
      onSuccess: (data) => {
          setJobId(data.job_id);
          // Don't auto-advance yet, let polling detect 'uploaded' or 'transcribing'
      }
  });

  const transcribeMutation = useMutation({
      mutationFn: () => jobs.transcribe(jobId!),
      onSuccess: () => {
          refetch();
      }
  });

  const planMutation = useMutation({
      mutationFn: () => jobs.plan(jobId!, srtContent),
      onSuccess: () => {
          refetch();
      }
  });

  const renderMutation = useMutation({
      mutationFn: () => jobs.render(jobId!, plan),
      onSuccess: () => {
          refetch();
      }
  });

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      uploadMutation.mutate(event.target.files[0]);
    }
  };

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0: // Upload
        if (jobId && jobStatus?.status !== 'uploaded') {
            // If already uploaded and moved past, show next step (handled by useEffect)
            // But if stuck here:
            return (
                 <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 8 }}>
                     <CircularProgress />
                     <Typography sx={{ mt: 2 }}>Initializing Job...</Typography>
                 </Box>
            );
        }

        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 8, border: '2px dashed #444', borderRadius: 2 }}>
                <CloudUploadIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                <Typography variant="h6" gutterBottom>Upload Raw Interview</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    MP4, MOV, MKV files supported
                </Typography>
                <Button
                    component="label"
                    variant="contained"
                    size="large"
                    disabled={uploadMutation.isPending}
                >
                    {uploadMutation.isPending ? 'Uploading...' : 'Select Video File'}
                    <input type="file" hidden accept="video/*" onChange={handleFileUpload} />
                </Button>
            </Box>
        );
      
      case 1: // Transcribe
        const isTranscribing = jobStatus?.status === 'transcribing' || transcribeMutation.isPending;
        const isTranscribed = jobStatus?.status === 'transcribed' || jobStatus?.status === 'planning' || jobStatus?.status === 'planned' || jobStatus?.status === 'rendering' || jobStatus?.status === 'done';

        if (!isTranscribed && !srtContent) {
             return (
                 <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 6 }}>
                     <DescriptionIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                     <Typography variant="h6" gutterBottom>Transcription Required</Typography>
                     <Typography variant="body2" color="text.secondary" sx={{ mb: 3, maxWidth: 400, textAlign: 'center' }}>
                         We need to transcribe the audio to text so you can edit the story. This uses Whisper AI.
                     </Typography>
                     
                     {!isTranscribing ? (
                         <Button variant="contained" onClick={() => transcribeMutation.mutate()} startIcon={<AutoAwesomeIcon />}>
                             Start Transcription
                         </Button>
                     ) : (
                         <Box sx={{ width: '100%', maxWidth: 400, textAlign: 'center' }}>
                             <LinearProgress sx={{ mb: 2 }} />
                             <Typography>Transcribing... this may take a few minutes.</Typography>
                         </Box>
                     )}
                 </Box>
             );
        }
        
        return (
            <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">Edit Transcript</Typography>
                    <Button 
                        variant="contained" 
                        onClick={() => planMutation.mutate()}
                        startIcon={planMutation.isPending ? <CircularProgress size={20} color="inherit" /> : <AutoAwesomeIcon />}
                        disabled={planMutation.isPending}
                    >
                        {planMutation.isPending ? 'Analyzing...' : 'Generate Cut Plan'}
                    </Button>
                </Box>
                <TextField 
                    fullWidth
                    multiline
                    rows={20}
                    value={srtContent}
                    onChange={(e) => setSrtContent(e.target.value)}
                    variant="outlined"
                    sx={{ fontFamily: 'monospace', bgcolor: 'background.paper' }}
                    placeholder="Transcript will appear here..."
                />
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    * You can edit the text directly. The AI will use this to find the best clips.
                </Typography>
            </Box>
        );

      case 2: // Plan
        const isPlanning = jobStatus?.status === 'planning' || planMutation.isPending;
        const isPlanned = jobStatus?.status === 'planned' || jobStatus?.status === 'rendering' || jobStatus?.status === 'done';
        
        if (isPlanning && !isPlanned) {
             return (
                 <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 6 }}>
                      <CircularProgress size={60} sx={{ mb: 3 }} />
                      <Typography variant="h6">Analyzing Story Structure...</Typography>
                      <Typography variant="body2" color="text.secondary">
                          Our AI is reading your transcript to identify the most compelling narrative arc.
                      </Typography>
                 </Box>
             );
        }

        return (
            <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">Proposed Cut List</Typography>
                    <Button 
                        variant="contained" 
                        color="secondary"
                        onClick={() => renderMutation.mutate()}
                        startIcon={renderMutation.isPending ? <CircularProgress size={20} color="inherit" /> : <MovieIcon />}
                        disabled={renderMutation.isPending}
                    >
                        {renderMutation.isPending ? 'Rendering...' : 'Render Final Video'}
                    </Button>
                </Box>
                <Paper variant="outlined" sx={{ maxHeight: 500, overflow: 'auto' }}>
                    <List>
                        {plan.map((clip: any, index: number) => (
                            <React.Fragment key={index}>
                                <ListItem alignItems="flex-start">
                                    <ListItemText 
                                        primary={
                                            <Typography variant="subtitle1" component="div">
                                                {clip.spoken_text || "(No spoken text)"}
                                            </Typography>
                                        }
                                        secondary={
                                            <Typography variant="caption" color="primary">
                                                {clip.start} — {clip.end}
                                            </Typography>
                                        }
                                    />
                                </ListItem>
                                <Divider component="li" />
                            </React.Fragment>
                        ))}
                    </List>
                </Paper>
            </Box>
        );

      case 3: // Render
        const isDone = jobStatus?.status === 'done' && finalVideoUrl;
        
        if (!isDone) {
             return (
                 <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 6 }}>
                      <CircularProgress size={60} sx={{ mb: 3 }} />
                      <Typography variant="h6">Rendering Video...</Typography>
                      <Typography variant="body2" color="text.secondary">
                          Stitching clips together using FFmpeg.
                      </Typography>
                 </Box>
             );
        }

        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
                <Typography variant="h4" gutterBottom color="primary">Story Cut Ready!</Typography>
                <Paper elevation={3} sx={{ p: 1, mb: 3, borderRadius: 2, overflow: 'hidden' }}>
                    <video 
                        controls 
                        src={finalVideoUrl || ""} 
                        style={{ maxWidth: '100%', maxHeight: '60vh', display: 'block' }} 
                    />
                </Paper>
                <Button 
                    variant="contained" 
                    color="primary" 
                    size="large"
                    href={finalVideoUrl || "#"} 
                    download
                    target="_blank"
                    startIcon={<DownloadIcon />}
                >
                    Download Video
                </Button>
                <Button 
                    variant="text" 
                    sx={{ mt: 2 }}
                    onClick={() => window.location.reload()}
                >
                    Start New Story
                </Button>
            </Box>
        );
        
      default:
        return 'Unknown step';
    }
  };

  return (
    <Box sx={{ width: '100%', maxWidth: 1200, margin: '0 auto' }}>
      <Typography variant="h4" gutterBottom component="div" sx={{ mb: 4, display: 'flex', alignItems: 'center', gap: 2 }}>
        <MovieIcon fontSize="large" color="secondary" />
        Story Studio
      </Typography>
      
      <Stepper activeStep={activeStep} sx={{ mb: 5 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>
      
      {jobStatus?.status === 'failed' && (
          <Alert severity="error" sx={{ mb: 3 }}>
              Error: {jobStatus.error || 'Operation failed'}
          </Alert>
      )}

      {/* Main Content Area */}
      <Paper sx={{ p: 4, minHeight: 400 }}>
        {renderStepContent(activeStep)}
      </Paper>
    </Box>
  );
}
