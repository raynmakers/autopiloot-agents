"use client";

import Link from "next/link";
import { useAuth } from "@/auth/useAuth";
import { Container, Typography, Button, Box, List, ListItem, ListItemText, Paper, CircularProgress } from "@mui/material";

export default function Home() {
  const { user, loading, isAuthenticated } = useAuth();

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h2" component="h1" gutterBottom>
        Next.js Firebase Template
      </Typography>
      
      <Box sx={{ my: 4 }}>
        {isAuthenticated ? (
          <Box>
            <Typography variant="h5" gutterBottom>
              Welcome, {user?.displayName || user?.email}!
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
              <Button 
                variant="contained" 
                component={Link} 
                href="/dashboard"
              >
                Go to Dashboard
              </Button>
              <Button 
                variant="outlined" 
                component={Link} 
                href="/profile"
              >
                Profile
              </Button>
            </Box>
          </Box>
        ) : (
          <Box>
            <Typography variant="h5" gutterBottom>
              Please sign in to continue
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
              <Button 
                variant="contained" 
                component={Link} 
                href="/signin"
              >
                Sign In
              </Button>
              <Button 
                variant="contained" 
                color="success" 
                component={Link} 
                href="/signup"
              >
                Sign Up
              </Button>
            </Box>
          </Box>
        )}
      </Box>

      <Paper sx={{ p: 3, mt: 6 }}>
        <Typography variant="h4" gutterBottom>
          Features
        </Typography>
        <List>
          <ListItem>
            <ListItemText primary="Firebase Authentication (Email/Password, Google, Anonymous)" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Firestore Database integration" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Firebase Storage for file uploads" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Firebase Functions support" />
          </ListItem>
          <ListItem>
            <ListItemText primary="State management with Jotai" />
          </ListItem>
          <ListItem>
            <ListItemText primary="TypeScript support" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Material-UI components" />
          </ListItem>
        </List>
      </Paper>
    </Container>
  );
}