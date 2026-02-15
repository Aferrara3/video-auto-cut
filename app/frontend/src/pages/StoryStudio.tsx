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
    Alert
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import { jobs } from '../api/client';
import { useMutation, useQuery } from '@tanstack/react-query';

const steps = ['Upload Interview', 'Review Transcript', 'Review Story Plan', 'Render'];

export default function StoryStudio() {
  const [activeStep, setActiveStep] = React.useState(0);
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [srtContent, setSrtContent] = React.useState<string>('');
  const [plan, setPlan] = React.useState<any[]>([]);
  const [finalVideoUrl, setFinalVideoUrl] = React.useState<string | null>(null);
  const [pollInterval, setPollInterval] = React.useState<number | false>(false);

  // Status Polling
  const { data: jobStatus } = useQuery({
      queryKey: ['jobStatus', jobId],
      queryFn: () => jobs.getStatus(jobId!),
      enabled: !!jobId && !!pollInterval,
      refetchInterval: pollInterval,
  });

  // Watch status changes to auto-advance or stop polling
  React.useEffect(() => {
      if (!jobStatus) return;

      if (activeStep === 1 && jobStatus.status === 'transcribed') {
          setSrtContent(jobStatus.srt_content || '');
          setPollInterval(false); // Stop polling
      }
      else if (activeStep === 2 && jobStatus.status === 'planned') {
          setPlan(jobStatus.plan || []);
          setPollInterval(false);
      }
      else if (activeStep === 3 && jobStatus.status === 'done') {
          setFinalVideoUrl(jobStatus.final_video_url);
          setPollInterval(false);
      }
      else if (jobStatus.status === 'failed') {
          setPollInterval(false);
      }
  }, [jobStatus, activeStep]);

  // Mutations
  const uploadMutation = useMutation({
      mutationFn: jobs.upload,
      onSuccess: (data) => {
          setJobId(data.job_id);
          handleNext();
      }
  });

  const transcribeMutation = useMutation({
      mutationFn: () => jobs.transcribe(jobId!),
      onSuccess: () => {
          setPollInterval(2000); // Start polling
      }
  });

  const planMutation = useMutation({
      mutationFn: () => jobs.plan(jobId!, srtContent),
      onSuccess: () => {
          handleNext(); // Move to Plan step view
          setPollInterval(2000); // Start polling
      }
  });

  const renderMutation = useMutation({
      mutationFn: () => jobs.render(jobId!, plan),
      onSuccess: () => {
          handleNext(); // Move to Render step view
          setPollInterval(2000);
      }
  });

  const handleNext = () => {
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      uploadMutation.mutate(event.target.files[0]);
    }
  };

  const handleTranscribeStart = () => {
      transcribeMutation.mutate();
  };
  
  const handlePlanStart = () => {
      planMutation.mutate();
  };

  const handleRenderStart = () => {
      renderMutation.mutate();
  };

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0: // Upload
        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
                <Typography variant="body1" gutterBottom>Upload your raw interview footage here.</Typography>
                <Button
                    component="label"
                    variant="contained"
                    size="large"
                    startIcon={uploadMutation.isPending ? <CircularProgress size={20} color="inherit" /> : <CloudUploadIcon />}
                    disabled={uploadMutation.isPending}
                >
                    Upload Video
                    <input type="file" hidden accept="video/*" onChange={handleFileUpload} />
                </Button>
            </Box>
        );
      
      case 1: // Transcribe
        if (!jobStatus || jobStatus.status === 'uploaded' || jobStatus.status === 'transcribing') {
             // Not started or In Progress
             const isTranscribing = jobStatus?.status === 'transcribing' || transcribeMutation.isPending;
             return (
                 <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
                     {!isTranscribing ? (
                         <Button variant="contained" onClick={handleTranscribeStart}>Start Transcription</Button>
                     ) : (
                         <>
                             <CircularProgress sx={{ mb: 2 }} />
                             <Typography>Transcribing video... this may take a while.</Typography>
                         </>
                     )}
                 </Box>
             );
        }
        // Done
        return (
            <Box>
                <Typography variant="subtitle1" gutterBottom>Edit Transcript (SRT Format)</Typography>
                <TextField 
                    fullWidth
                    multiline
                    rows={15}
                    value={srtContent}
                    onChange={(e) => setSrtContent(e.target.value)}
                    variant="outlined"
                    sx={{ fontFamily: 'monospace' }}
                />
            </Box>
        );

      case 2: // Plan
        if (!jobStatus || jobStatus.status === 'transcribed' || jobStatus.status === 'planning') {
             const isPlanning = jobStatus?.status === 'planning' || planMutation.isPending;
             return (
                 <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
                      <CircularProgress sx={{ mb: 2 }} />
                      <Typography>Generating Story Plan with AI...</Typography>
                 </Box>
             );
        }
        // Planned
        return (
            <Box>
                <Typography variant="subtitle1" gutterBottom>Proposed Story Cut List</Typography>
                <Paper variant="outlined" sx={{ maxHeight: 400, overflow: 'auto' }}>
                    <List>
                        {plan.map((clip: any, index: number) => (
                            <React.Fragment key={index}>
                                <ListItem>
                                    <ListItemText 
                                        primary={clip.spoken_text}
                                        secondary={`${clip.start} - ${clip.end}`}
                                    />
                                </ListItem>
                                <Divider />
                            </React.Fragment>
                        ))}
                    </List>
                </Paper>
            </Box>
        );

      case 3: // Render
        if (!jobStatus || jobStatus.status === 'planned' || jobStatus.status === 'rendering') {
             return (
                 <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
                      <CircularProgress sx={{ mb: 2 }} />
                      <Typography>Rendering final video...</Typography>
                 </Box>
             );
        }
        // Done
        return (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
                <Typography variant="h5" gutterBottom>Video Ready!</Typography>
                {finalVideoUrl && (
                    <video 
                        controls 
                        src={`/api${finalVideoUrl}`} 
                        style={{ maxWidth: '100%', maxHeight: 400, marginBottom: 16 }} 
                    />
                )}
                <Button 
                    variant="contained" 
                    color="primary" 
                    href={`/api${finalVideoUrl}`} 
                    download
                    target="_blank"
                >
                    Download Video
                </Button>
            </Box>
        );
        
      default:
        return 'Unknown step';
    }
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h4" sx={{ mb: 3 }}>Story Studio</Typography>
      
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>
      
      {jobStatus?.status === 'failed' && (
          <Alert severity="error" sx={{ mb: 2 }}>
              Error: {jobStatus.error || 'Operation failed'}
          </Alert>
      )}

      <Paper sx={{ p: 4, minHeight: 300 }}>
        {renderStepContent(activeStep)}
        
        {/* Navigation Buttons */}
        <Box sx={{ display: 'flex', flexDirection: 'row', pt: 2, mt: 2, borderTop: 1, borderColor: 'divider' }}>
          <Button
            color="inherit"
            disabled={activeStep === 0 || activeStep === 3} // Can't go back from final? Or maybe yes.
            onClick={handleBack}
            sx={{ mr: 1 }}
          >
            Back
          </Button>
          <Box sx={{ flex: '1 1 auto' }} />
          
          {/* Custom Next Actions based on State */}
          {activeStep === 1 && jobStatus?.status === 'transcribed' && (
               <Button onClick={handlePlanStart} variant="contained">
                   Generate Plan
               </Button>
          )}
          
          {activeStep === 2 && jobStatus?.status === 'planned' && (
               <Button onClick={handleRenderStart} variant="contained">
                   Render Video
               </Button>
          )}
          
          {activeStep === 3 && jobStatus?.status === 'done' && (
              <Button onClick={() => window.location.reload()}>Start Over</Button>
          )}

        </Box>
      </Paper>
    </Box>
  );
}