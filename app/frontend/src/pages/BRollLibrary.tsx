import React from 'react';
import { 
  Box, 
  Typography, 
  Button, 
  TextField, 
  ImageList, 
  ImageListItem, 
  ImageListItemBar,
  IconButton,
  CircularProgress,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import InfoIcon from '@mui/icons-material/Info';
import CloseIcon from '@mui/icons-material/Close';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { broll } from '../api/client';

// Define interface for b-roll item
interface BRollItem {
  id: string;
  description: string;
  timestamp: number;
  duration?: number;
  end_timestamp?: number;
  keyframe_path: string;
  video_path: string; // Absolute path from backend
  image_filename: string;
  match_type?: string;
  score?: number;
}

export default function BRollLibrary() {
  const [searchQuery, setSearchQuery] = React.useState('');
  const [semanticQuery, setSemanticQuery] = React.useState('');
  const [searchMode, setSearchMode] = React.useState<'quick' | 'semantic'>('quick');
  const [selectedItem, setSelectedItem] = React.useState<BRollItem | null>(null);
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const queryClient = useQueryClient();

  // Fetch ALL items initially and keep them cached
  // This is efficient for small-medium libraries (up to few thousand items)
  const { data: allItemsData, isLoading: isLoadingAll } = useQuery({
    queryKey: ['broll', 'all'],
    queryFn: broll.getAll,
  });

  // Semantic search query - only runs when semanticQuery is set
  const { data: semanticData, isLoading: isLoadingSemantic } = useQuery({
    queryKey: ['broll', 'semantic', semanticQuery],
    queryFn: () => broll.search(semanticQuery),
    enabled: searchMode === 'semantic' && !!semanticQuery,
  });

  // Determine which items to show
  const displayItems = React.useMemo(() => {
    if (searchMode === 'semantic') {
        return semanticData?.results || [];
    } else {
        // Quick mode: Client-side filter
        const allItems = allItemsData?.items || [];
        if (!searchQuery) return allItems;
        
        const lowerQuery = searchQuery.toLowerCase();
        return allItems.filter((item: BRollItem) => 
            item.description.toLowerCase().includes(lowerQuery)
        );
    }
  }, [searchMode, searchQuery, allItemsData, semanticData]);

  const isLoading = searchMode === 'semantic' ? isLoadingSemantic : isLoadingAll;

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
        setSearchMode('semantic');
        setSemanticQuery(searchQuery);
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchQuery(e.target.value);
      if (searchMode === 'semantic') {
          // Reset to quick mode immediately on typing
          setSearchMode('quick'); 
      }
  };

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: broll.ingest,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['broll'] });
    },
  });

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      uploadMutation.mutate(event.target.files[0]);
    }
  };

  const handleInfoClick = (item: BRollItem) => {
    setSelectedItem(item);
  };

  const handleClose = () => {
    setSelectedItem(null);
  };
  
  // Effect to sync video time when modal opens
  React.useEffect(() => {
    if (selectedItem && videoRef.current) {
        // We need to serve the video file. The backend path is absolute.
        // We need a way to serve it. 
        // Current backend serves /files/{filename}.
        // We can extract filename from video_path.
        videoRef.current.currentTime = selectedItem.timestamp;
    }
  }, [selectedItem]);

  const items = displayItems;

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3, alignItems: 'center' }}>
        <Typography variant="h4">B-Roll Library</Typography>
        <Button
          component="label"
          variant="contained"
          startIcon={uploadMutation.isPending ? <CircularProgress size={20} color="inherit" /> : <CloudUploadIcon />}
          disabled={uploadMutation.isPending}
        >
          Upload Video
          <input
            type="file"
            hidden
            accept="video/*"
            onChange={handleFileUpload}
          />
        </Button>
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-end' }}>
          <SearchIcon sx={{ color: 'action.active', mr: 1, my: 0.5 }} />
          <TextField 
            fullWidth 
            label="Search B-Roll" 
            placeholder="Type for quick match, press Enter for semantic search..."
            variant="standard" 
            value={searchQuery}
            onChange={handleSearchChange}
            onKeyDown={handleSearchKeyDown}
            helperText={searchMode === 'semantic' ? "Semantic Search Active" : "Quick Search Active"}
          />
        </Box>
      </Paper>

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 5 }}>
          <CircularProgress />
        </Box>
      ) : (
        <ImageList variant="masonry" cols={3} gap={8}>
          {items.map((item: BRollItem) => (
            <ImageListItem key={item.id}>
              <img
                src={`${item.keyframe_path}?w=248&fit=crop&auto=format`}
                srcSet={`${item.keyframe_path}?w=248&fit=crop&auto=format&dpr=2 2x`}
                alt={item.description}
                loading="lazy"
                style={{ cursor: 'pointer' }}
                onClick={() => handleInfoClick(item)}
              />
              <ImageListItemBar
                title={item.description}
                subtitle={
                  <Box component="span" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <span>@ {item.timestamp.toFixed(1)}s</span>
                    {item.match_type === 'semantic' && (
                       <Chip size="small" label="Semantic Match" color="primary" sx={{ height: 16, fontSize: '0.6rem' }} />
                    )}
                  </Box>
                }
                actionIcon={
                  <IconButton
                    sx={{ color: 'rgba(255, 255, 255, 0.54)' }}
                    aria-label={`info about ${item.description}`}
                    onClick={() => handleInfoClick(item)}
                  >
                    <InfoIcon />
                  </IconButton>
                }
              />
            </ImageListItem>
          ))}
        </ImageList>
      )}
      
      {!isLoading && items.length === 0 && (
        <Typography variant="body1" sx={{ textAlign: 'center', mt: 5, color: 'text.secondary' }}>
          No B-roll found. Upload a video to get started.
        </Typography>
      )}

      {/* Metadata Dialog */}
      <Dialog open={!!selectedItem} onClose={handleClose} maxWidth="md" fullWidth>
        {selectedItem && (
            <>
                <DialogTitle sx={{ m: 0, p: 2 }}>
                    {selectedItem.description}
                    <IconButton
                        aria-label="close"
                        onClick={handleClose}
                        sx={{
                            position: 'absolute',
                            right: 8,
                            top: 8,
                            color: (theme) => theme.palette.grey[500],
                        }}
                    >
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent dividers>
                    <Box sx={{ mb: 2 }}>
                        <Typography variant="subtitle2" gutterBottom>Preview Segment ({selectedItem.timestamp.toFixed(1)}s - {selectedItem.end_timestamp?.toFixed(1)}s)</Typography>
                        <video 
                            ref={videoRef}
                            controls 
                            style={{ width: '100%', maxHeight: '400px', backgroundColor: '#000' }}
                            src={`/files/${selectedItem.video_path.split('/').pop()}`}
                            onLoadedMetadata={(e) => {
                                e.currentTarget.currentTime = selectedItem.timestamp;
                            }}
                        />
                    </Box>
                    <Typography variant="h6" gutterBottom>Metadata</Typography>
                    <Typography variant="body2"><strong>ID:</strong> {selectedItem.id}</Typography>
                    <Typography variant="body2"><strong>Source Video:</strong> {selectedItem.video_path.split('/').pop()}</Typography>
                    <Typography variant="body2"><strong>Timestamp:</strong> {selectedItem.timestamp.toFixed(2)}s</Typography>
                    <Typography variant="body2"><strong>Duration:</strong> {selectedItem.duration?.toFixed(2)}s</Typography>
                    <Typography variant="body2"><strong>Description:</strong> {selectedItem.description}</Typography>
                    {selectedItem.score && (
                        <Typography variant="body2"><strong>Search Score:</strong> {selectedItem.score.toFixed(3)} ({selectedItem.match_type})</Typography>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleClose}>Close</Button>
                </DialogActions>
            </>
        )}
      </Dialog>
    </Box>
  );
}