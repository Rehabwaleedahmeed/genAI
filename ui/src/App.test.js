import { render, screen } from '@testing-library/react';
import App from './App';

test('renders app title and cook button', () => {
  render(<App />);
  expect(screen.getByText(/ai chef/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /cook/i })).toBeInTheDocument();
});
