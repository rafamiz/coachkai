import { getServiceClient } from './client';
import { User } from '../types/user';

export async function getUserByPhone(phone: string): Promise<User | null> {
  const { data } = await getServiceClient()
    .from('users')
    .select('*')
    .eq('phone', phone)
    .single();
  return data;
}

export async function getUserById(id: string): Promise<User | null> {
  const { data } = await getServiceClient()
    .from('users')
    .select('*')
    .eq('id', id)
    .single();
  return data;
}

export async function updateUser(id: string, updates: Partial<User>): Promise<User | null> {
  const { data } = await getServiceClient()
    .from('users')
    .update({ ...updates, updated_at: new Date().toISOString() })
    .eq('id', id)
    .select()
    .single();
  return data;
}

export async function createUser(user: Partial<User>): Promise<User | null> {
  const { data } = await getServiceClient()
    .from('users')
    .insert(user)
    .select()
    .single();
  return data;
}
