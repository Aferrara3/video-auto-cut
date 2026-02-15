import * as React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import Card from '@mui/material/Card';
import CardMedia from '@mui/material/CardMedia';
import CardContent from '@mui/material/CardContent';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import IconButton from '@mui/material/IconButton';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import MovieCreationIcon from '@mui/icons-material/MovieCreation';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { action as actionApi } from '../api/client';

const steps = ['Upload Video', 'Analyze Content', 'Select Highlights', 'Render Video'];

interface Segment {
  id: string;
  timestamp: number;
  end_timestamp: number;
  duration: number;
  description: string;
  image_url: string;
  frame_number: number;
  selection_reason?: string;
}

interface ActionJob {
  id: string;
  status: string;
  updatedAt: number;
  error?: string;
}

const JOBS_STORAGE_KEY = 'action_jobs';

const loadJobs = (): ActionJob[] => {
  try {
    const raw = localStorage.getItem(JOBS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

export default function ActionStudio() {
  const [activeStep, setActiveStep] = React.useState(0);
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [status, setStatus] = React.useState('idle');
  const [segments, setSegments] = React.useState<Segment[]>([]);
  const [plan, setPlan] = React.useState<Segment[]>([]);
  const [finalVideoUrl, setFinalVideoUrl] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [jobHistory, setJobHistory] = React.useState<ActionJob[]>(() => loadJobs());

  const upsertJob = React.useCallback((id: string, nextStatus: string, error?: string) => {
    setJobHistory((prev) => {
      const next: ActionJob[] = [
        { id, status: nextStatus, updatedAt: Date.now(), error },
        ...prev.filter((j) => j.id !== id),
      ].slice(0, 20);
      localStorage.setItem(JOBS_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const removeJob = React.useCallback((id: string) => {
    setJobHistory((prev) => {
      const next = prev.filter((j) => j.id !== id);
      localStorage.setItem(JOBS_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const hydrateFromStatus = React.useCallback((data: any, targetJobId: string) => {
    setJobId(targetJobId);
    setStatus(data.status || 'idle');
    upsertJob(targetJobId, data.status || 'idle', data.error);
    if (data.status === 'ingesting') setActiveStep(1);
    if (data.status === 'ingested' || data.status === 'planning' || data.status === 'planned') setActiveStep(2);
    if (data.status === 'rendering' || data.status === 'done') setActiveStep(3);
    if (data.segments) setSegments(data.segments);
    if (data.plan) setPlan(data.plan);
    if (data.final_video_url) setFinalVideoUrl(data.final_video_url);
    if (data.error) setError(data.error);
  }, [upsertJob]);

  React.useEffect(() => {
    const savedJobId = localStorage.getItem('action_job_id');
    if (!savedJobId) return;
    actionApi.getStatus(savedJobId).then((data) => {
      if (data?.status && data.status !== 'not_found') {
        hydrateFromStatus(data, savedJobId);
      } else {
        localStorage.removeItem('action_job_id');
        removeJob(savedJobId);
      }
    }).catch(() => {});
    // intentionally run once on initial mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrateFromStatus, removeJob]);

  React.useEffect(() => {
    const activeJobs = jobHistory.filter((j) => ['ingesting', 'planning', 'rendering'].includes(j.status));
    if (activeJobs.length === 0) return;
    const id = setInterval(async () => {
      for (const job of activeJobs) {
        try {
          const data = await actionApi.getStatus(job.id);
          if (data?.status === 'not_found') {
            removeJob(job.id);
          } else if (data?.status) {
            upsertJob(job.id, data.status, data.error);
          }
        } catch {}
      }
    }, 5000);
    return () => clearInterval(id);
  }, [jobHistory, upsertJob, removeJob]);

  React.useEffect(() => {
    if (!jobId || !['ingesting', 'planning', 'rendering'].includes(status)) return;

    const id = setInterval(async () => {
        try {
          const data = await actionApi.getStatus(jobId);
          if (data?.status === 'not_found') {
            removeJob(jobId);
            handleStartNewJob();
            setError('This job expired after backend restart. Start a new job.');
            return;
          }
          hydrateFromStatus(data, jobId);
        } catch {
          setError('Polling failed');
          setStatus('failed');
      }
    }, 2000);

    return () => clearInterval(id);
  }, [jobId, status, hydrateFromStatus]);

  React.useEffect(() => {
    if (jobId) localStorage.setItem('action_job_id', jobId);
  }, [jobId]);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files?.[0]) return;
    try {
      const data = await actionApi.ingest(event.target.files[0]);
      setJobId(data.job_id);
      setStatus('ingesting');
      upsertJob(data.job_id, 'ingesting');
      setActiveStep(1);
      setError(null);
      setPlan([]);
      setSegments([]);
      setFinalVideoUrl(null);
    } catch (e: any) {
      setError(e?.message || 'Upload failed');
      setStatus('failed');
    }
  };

  const handleGeneratePlan = async () => {
    if (!jobId) return;
    try {
      setStatus('planning');
      upsertJob(jobId, 'planning');
      const data = await actionApi.plan(jobId);
      setPlan(data.plan || []);
      setStatus('planned');
      upsertJob(jobId, 'planned');
    } catch (e: any) {
      setError(e?.message || 'Plan failed');
      setStatus('failed');
      upsertJob(jobId, 'failed', e?.message || 'Plan failed');
    }
  };

  const handleResumeJob = async (targetJobId: string) => {
    try {
      const data = await actionApi.getStatus(targetJobId);
      if (data?.status === 'not_found') {
        removeJob(targetJobId);
        if (jobId === targetJobId) handleStartNewJob();
        setError('That job is no longer available (backend likely restarted).');
        return;
      }
      setError(null);
      hydrateFromStatus(data, targetJobId);
    } catch {
      setError('Failed to resume job');
    }
  };

  const handleRender = async () => {
    if (!jobId || plan.length === 0) return;
    try {
      setStatus('rendering');
      upsertJob(jobId, 'rendering');
      setActiveStep(3);
      await actionApi.render(jobId, plan);
    } catch (e: any) {
      setError(e?.message || 'Render failed');
      setStatus('failed');
      upsertJob(jobId, 'failed', e?.message || 'Render failed');
    }
  };

  const handleStartNewJob = () => {
    setJobId(null);
    setStatus('idle');
    setActiveStep(0);
    setSegments([]);
    setPlan([]);
    setFinalVideoUrl(null);
    setError(null);
    localStorage.removeItem('action_job_id');
  };

  const handleDeleteJob = (targetJobId: string) => {
    removeJob(targetJobId);
    if (jobId === targetJobId) {
      handleStartNewJob();
    }
  };

  const toggleSegment = (segment: Segment) => {
    setPlan((prev) => {
      const exists = prev.some((p) => p.id === segment.id);
      const next = exists
        ? prev.filter((p) => p.id !== segment.id)
        : [...prev, { ...segment, selection_reason: 'Manual selection' }];
      return next.sort((a, b) => a.timestamp - b.timestamp);
    });
  };

  const statusColor = (s: string): 'default' | 'primary' | 'success' | 'warning' | 'error' =>
    s === 'done' ? 'success' : s === 'failed' ? 'error' : ['planning', 'rendering', 'ingesting'].includes(s) ? 'warning' : 'default';

  return (
    <Box sx={{ width: '100%', maxWidth: 1400, margin: '0 auto', display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 320px' }, gap: 3 }}>
      <Box>
      <Box sx={{ mb: 4, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
        <Typography variant="h4" sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <AutoFixHighIcon fontSize="large" color="primary" />
          Action Studio
        </Typography>
        <Button variant="outlined" onClick={handleStartNewJob}>Start New Job</Button>
      </Box>

      <Stepper activeStep={activeStep} sx={{ mb: 5 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error && (
        <Box sx={{ p: 2, mb: 2, bgcolor: 'error.dark', color: 'error.contrastText', borderRadius: 1 }}>
          Error: {error}
        </Box>
      )}

      {['ingesting', 'planning', 'rendering'].includes(status) && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            {status === 'planning' ? 'Auto-detecting highlights...' : status === 'ingesting' ? 'Analyzing footage...' : 'Rendering video...'}
          </Typography>
          <LinearProgress />
        </Box>
      )}

      {activeStep === 0 && (
        <Box sx={{ textAlign: 'center', py: 8, border: '2px dashed #444', borderRadius: 2 }}>
          <input accept="video/*" style={{ display: 'none' }} id="action-upload" type="file" onChange={handleUpload} />
          <label htmlFor="action-upload">
            <Button variant="contained" component="span" startIcon={<CloudUploadIcon />} size="large">
              Upload Action Footage
            </Button>
          </label>
        </Box>
      )}

      {activeStep === 1 && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <CircularProgress size={60} />
          <Typography variant="h6" sx={{ mt: 3 }}>Analyzing video content...</Typography>
          <Box sx={{ width: '50%', margin: '20px auto' }}>
            <LinearProgress />
          </Box>
        </Box>
      )}

      {activeStep === 2 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Typography variant="h6">Found {segments.length} segments</Typography>
            <Button
              variant="contained"
              onClick={plan.length > 0 ? handleRender : handleGeneratePlan}
              startIcon={plan.length > 0 ? <MovieCreationIcon /> : <AutoFixHighIcon />}
              disabled={status === 'planning' || status === 'rendering'}
            >
              {status === 'planning' ? 'Detecting...' : plan.length > 0 ? 'Render Video' : 'Auto-Detect Highlights'}
            </Button>
          </Box>

          <Typography variant="subtitle1" sx={{ mb: 2 }}>Click segments to select/deselect highlights</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {segments.map((seg) => {
              const selected = plan.some((p) => p.id === seg.id);
              return (
                <Box key={seg.id} sx={{ width: { xs: '48%', sm: '31%', md: '23%' } }}>
                  <Card
                    sx={{
                      opacity: selected ? 1 : 0.6,
                      border: selected ? '2px solid #90caf9' : 'none',
                      cursor: 'pointer',
                    }}
                    onClick={() => toggleSegment(seg)}
                  >
                    <CardMedia component="img" height="100" image={seg.image_url} alt="Segment thumbnail" />
                    <CardContent sx={{ p: 1 }}>
                      <Typography variant="caption" display="block" color="text.secondary">
                        {seg.timestamp.toFixed(1)}s ({seg.duration.toFixed(1)}s)
                      </Typography>
                      <Typography variant="caption">{seg.description}</Typography>
                    </CardContent>
                  </Card>
                </Box>
              );
            })}
          </Box>
        </Box>
      )}

      {activeStep === 3 && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          {status === 'rendering' ? (
            <>
              <CircularProgress size={60} />
              <Typography sx={{ mt: 2 }}>Rendering Highlights...</Typography>
            </>
          ) : finalVideoUrl ? (
            <>
              <Typography variant="h5" color="success.main" gutterBottom>Action Cut Ready!</Typography>
              <video controls width="100%" style={{ maxHeight: '60vh', borderRadius: 8, marginBottom: 20 }} src={finalVideoUrl} />
              <Button variant="contained" href={finalVideoUrl} download startIcon={<DownloadIcon />}>
                Download Video
              </Button>
            </>
          ) : (
            <Typography color="error">Something went wrong during rendering.</Typography>
          )}
        </Box>
      )}
      </Box>

      <Paper sx={{ p: 2, height: 'fit-content', position: { md: 'sticky' }, top: { md: 88 }, borderRadius: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>Jobs</Typography>
        <Typography variant="caption" color="text.secondary">Resume or monitor action jobs</Typography>
        <Button fullWidth variant="outlined" sx={{ mt: 1 }} onClick={handleStartNewJob}>New Job</Button>
        <Divider sx={{ my: 1.5 }} />
        <Stack spacing={1}>
          {jobHistory.length === 0 && (
            <Typography variant="body2" color="text.secondary">No jobs yet.</Typography>
          )}
          {jobHistory.map((job) => (
            <Box
              key={job.id}
              onClick={() => handleResumeJob(job.id)}
              sx={{
                p: 1.2,
                borderRadius: 1.5,
                bgcolor: job.id === jobId ? 'action.selected' : 'background.default',
                cursor: 'pointer',
                border: '1px solid',
                borderColor: 'divider',
                '&:hover': { borderColor: 'primary.main' },
              }}
            >
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                  {job.id.slice(0, 8)}...{job.id.slice(-4)}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Chip size="small" label={job.status} color={statusColor(job.status)} />
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteJob(job.id);
                    }}
                  >
                    <DeleteOutlineIcon fontSize="inherit" />
                  </IconButton>
                </Box>
              </Box>
              <Typography variant="caption" color="text.secondary">
                {new Date(job.updatedAt).toLocaleTimeString()}
              </Typography>
              {job.error && (
                <Typography variant="caption" color="error" sx={{ display: 'block' }}>
                  {job.error}
                </Typography>
              )}
            </Box>
          ))}
        </Stack>
      </Paper>
    </Box>
  );
}
