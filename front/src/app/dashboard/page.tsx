"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/auth/useAuth";
import { authOperations } from "@/auth/authOperations";
import {
  Container,
  Typography,
  Button,
  Box,
  Paper,
  Grid,
  Card,
  CardContent,
  CardActions,
} from "@mui/material";
import { Person, Storage, Functions, CloudUpload } from "@mui/icons-material";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      router.push("/signin");
    }
  }, [loading, isAuthenticated, router]);

  const handleSignOut = async () => {
    try {
      await authOperations.signOut();
      router.push("/");
    } catch (error) {
      console.error("Failed to sign out:", error);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 4 }}>
        <Typography variant="h4" component="h1">
          Dashboard
        </Typography>
        <Button variant="outlined" color="error" onClick={handleSignOut}>
          Sign Out
        </Button>
      </Box>

      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Welcome back, {user?.displayName || user?.email}!
        </Typography>
        <Typography variant="body1" color="text.secondary">
          User ID: {user?.uid}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Email verified: {user?.emailVerified ? "Yes" : "No"}
        </Typography>
      </Paper>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <Person color="primary" sx={{ mr: 2 }} />
                <Typography variant="h6">Profile</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Manage your user profile and settings
              </Typography>
            </CardContent>
            <CardActions>
              <Button size="small">View Profile</Button>
            </CardActions>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <Storage color="primary" sx={{ mr: 2 }} />
                <Typography variant="h6">Database</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Firestore database operations
              </Typography>
            </CardContent>
            <CardActions>
              <Button size="small">Explore</Button>
            </CardActions>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <CloudUpload color="primary" sx={{ mr: 2 }} />
                <Typography variant="h6">Storage</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Upload and manage files
              </Typography>
            </CardContent>
            <CardActions>
              <Button size="small">Upload Files</Button>
            </CardActions>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                <Functions color="primary" sx={{ mr: 2 }} />
                <Typography variant="h6">Functions</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Call Firebase Functions
              </Typography>
            </CardContent>
            <CardActions>
              <Button size="small">Test Function</Button>
            </CardActions>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
}