import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '../../store/authStore';

describe('authStore', () => {
  beforeEach(() => {
    // Reset store before each test
    useAuthStore.setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    });
  });

  it('should initialize with default state', () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  it('should set tokens and authenticate', () => {
    useAuthStore.getState().setTokens('access123', 'refresh456');
    const state = useAuthStore.getState();
    
    expect(state.accessToken).toBe('access123');
    expect(state.refreshToken).toBe('refresh456');
    expect(state.isAuthenticated).toBe(true);
  });

  it('should set user', () => {
    const mockUser = {
      id: '1',
      email: 'test@example.com',
      username: 'testuser',
      full_name: 'Test User',
      avatar_url: null,
      role: 'user'
    };
    
    useAuthStore.getState().setUser(mockUser);
    const state = useAuthStore.getState();
    
    expect(state.user).toEqual(mockUser);
  });

  it('should clear state on logout', () => {
    // Setup initial state
    useAuthStore.setState({
      user: {
        id: '1',
        email: 'test@example.com',
        username: 'testuser',
        full_name: 'Test User',
        avatar_url: null,
        role: 'user'
      },
      accessToken: 'access123',
      refreshToken: 'refresh456',
      isAuthenticated: true,
    });

    // Act
    useAuthStore.getState().logout();

    // Assert
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });
});
