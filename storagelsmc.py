# -*- coding: utf-8 -*-
"""StorageLSMC.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1GgWoopDD_3YRv-u33Vc2NDVaaAmWCSLV

## Valuation of Energy Storage
"""

import IPython as ip
import logging
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")
from past.builtins import xrange
from sys import version 
import seaborn as sns
import pandas as pd
import json
from io import StringIO

class StorageLSMC6(object):
    """ Class for Energy Storage option pricing using Alexander Boogert & Cyriel De Jong (2008):
    "Ref."
    S0 : float : initial stock/index level
    T : float : time to maturity (in year fractions)
    M : int : grid or granularity for time (in number of total points)
    gamma : float : constant risk-free short rate
    div :    float : dividend yield
    sigma :  float : volatility factor in diffusion term
    I_max: int : maximum inventory level
    I_min : int : minimum inventory level
    DCQ: int : daily injection/withdrawal contract quantity
    simulations : int : number of simulated price paths
    deg : int : degree of the polynomial used in the regression
    price_given : float : matrix of prices (i.e. historical prices), default is not given, hence, randomly generated using brownian motion
    logg : string : user choice of logging; detailed steps of the algorithms for debugging purposes
    """

    def __init__(self, S0, T, M, gamma, div, sigma, I_max, I_min, DCQ, simulations, deg, providedPrice_matrix, logg= None):
        try:
            self.S0 = float(S0)
            # self.strike = float(strike)
            assert T > 0
            self.T = float(T)
            assert M > 0
            self.M = int(M)
            assert gamma >= 0
            self.gamma = float(gamma)
            assert div >= 0
            self.div = float(div)
            assert sigma > 0
            self.sigma = float(sigma)
            assert DCQ > 0
            self.DCQ = int(DCQ)
            assert I_max > 0
            self.I_max = int(I_max)
            assert I_min >= 0
            self.I_min = int(I_min)
            assert simulations > 0
            self.simulations = int(simulations)
            assert deg > 0
            self.deg = int(deg)
            self.providedPrice_matrix = providedPrice_matrix
            self.logg = logg
        except ValueError:
            logging.error('Error passing Options parameters')

        if S0 < 0 or T <= 0 or M <= 0 or gamma < 0 or div < 0 or sigma < 0 or I_max <=0 or I_min < 0 or DCQ <= 0 or simulations <=0 or deg <= 0:
            raise ValueError('Error: Negative inputs not allowed')

        self.time_unit = self.T / float(self.M)
        self.discount = 1
        self.simulations_changed = False
        # np.exp(-self.gamma * self.time_unit)
        self.actions = [-self.DCQ, 0, self.DCQ]
        self.inventory_max = int(I_max)
        self.inventory_min = int(I_min)
        self.inventoryGridSpace = np.arange(((self.inventory_max - self.inventory_min)//self.DCQ)+1)
        self.inventorySpace = np.arange(self.inventory_min, self.inventory_max+1, self.DCQ)

    def is_odd(self, num):
        return num & 1 and True or False

    def MCprice_matrix(self, seed = 123):
        """ Returns MC price matrix rows: time columns: price-path simulation """
        np.random.seed(seed)
        if self.is_odd(self.simulations):
            self.simulations += 1; #[-1,1][random.randrange(2)]
            self.simulations_changed = True;
        MCprice_matrix = np.zeros((self.M + 1, self.simulations), dtype=np.float64)
        MCprice_matrix[0,:] = self.S0
        for t in xrange(1, self.M + 1):
            brownian = np.random.standard_normal(int(self.simulations / 2))
            brownian = np.concatenate((brownian, -brownian))
            MCprice_matrix[t, :] = (MCprice_matrix[t - 1, :]
                                  * np.exp((self.gamma - self.sigma ** 2 / 2.) * self.time_unit
                                  + self.sigma * brownian * np.sqrt(self.time_unit)))
        if self.simulations_changed:
          MCprice_matrix = MCprice_matrix[:,:-1]
          self.simulations -= self.simulations
        return MCprice_matrix


    def payoff(action,inv_level,t):
        """injection cost or withdrawal revenue @ time = t, inventory = inv_level"""
        withdraw = -action*self.MCprices[t,:]
        inject = -action*self.MCprices[t,:]
        
        return np.where(action>0, withdraw+self.discount*self.V_copy[inv_level-1,:], inject+self.discount*self.V_copy[inv_level+1,:])

    @property
    def value_vector(self):
        if self.providedPrice_matrix is None:
          self.MCprices = np.copy(self.MCprice_matrix()[1:,:])
        else:
          self.MCprices = np.copy(self.providedPrice_matrix)
          self.MCprices = self.MCprices[1:,:]
        
        self.MCprices = np.concatenate((np.array([self.MCprices[0,:]]),self.MCprices),axis=0)
        T = self.MCprices.shape[0]-1
        sims = self.MCprices.shape[1]
        self.h = np.zeros((len(self.actions),sims))
        Value = np.ones((self.inventoryGridSpace[-1]+1,sims))*-10
        Value[0,:] = 0  # <-------- This is V_{T+1}
        self.policy = np.zeros((T+1,self.inventoryGridSpace[-1]+1,sims))

        tau = self.DCQ*np.ceil((T+1)/2)
        rho = self.DCQ*np.ceil((T+2)/2)
        z = -float("inf")
        infty = np.zeros_like([Value[0,:]])
        infty[:] = z
        i_max_prev = 0; i_max_current = 0
        u_t ='-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------\n';
        l_t ='\n-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------'
        u_i = '+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n'
        l_i = '\n+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++'
        p_i = '|'
        logger = logging.getLogger('iteration')
        if self.logg == 'info':
          logger.setLevel(level=logging.INFO)
        elif self.logg == 'debug':
          logger.setLevel(level=logging.DEBUG)
        else:
          logger.setLevel(level=logging.ERROR)
        for t in range(T, 0 , -1):
          V_copy = np.copy(Value)    
          Value = np.ones((self.inventoryGridSpace[-1]+1,sims))*-10
          Value[0,:] = 0 
          
          i_max_prev = i_max_current
          i_max_current = int(max(min((self.inventory_max//self.DCQ)+1, (tau - abs(self.DCQ*t - rho))//self.DCQ), min((self.inventory_max//self.DCQ)+1, (tau - abs(self.DCQ*t - tau))//self.DCQ)))
          Inventory_permissible = range(0, i_max_current)
          logger.info('\n {a} t ={b}, X ={c}{d}'.format(a=u_t,b=t,c=self.MCprices[t,:],d=l_t))
          for i in Inventory_permissible:  # <-------- only loop over permissible inventory states
            self.h_inj = np.zeros((len(self.actions),sims))
            self.h_wdra = np.zeros((len(self.actions),sims))
            self.h_inj[:] = np.nan
            self.h_wdra[:] = np.nan
            X = self.MCprices[t,:]
            logger.info('\n {d} t = {a}, and i = {b}{c}'.format(d=u_i, a=t, b=i, c=l_i))

            if i == 0:
              Y_inj = self.discount*V_copy[i+1,:]
              logger.info(' Y_inject= {a}'.format(a=Y_inj))
              regression_inj = np.polyfit(X, Y_inj, self.deg)
              continuation_value_inj = np.polyval(regression_inj, X)  
              logger.info(' continuation_inject = {a}'.format(a=continuation_value_inj))
              self.h_inj[2,:] = -self.actions[2]*self.MCprices[t,:] + continuation_value_inj
              logger.info(' h_inject = {a}'.format(a=self.h_inj))
              idx_inj = np.nanargmax(self.h_inj, axis=0)
              logger.info(' indices_inject = {a}'.format(a=idx_inj))
              val_inj = np.nanmax(self.h_inj, axis=0)
              optimal_action_inj = np.empty(sims) 
              for k in range(len(idx_inj)):
                optimal_action_inj[k] = -self.actions[int(idx_inj[k])]
              
              continuation_value_wdra = infty  
              logger.info(' continuation_withdraw = {a}'.format(a=continuation_value_wdra))            
              self.h_wdra[0,:] = -self.actions[0]*self.MCprices[t,:] + continuation_value_wdra
              idx_wdra = np.nanargmax(self.h_wdra, axis=0)
              val_wdra = np.nanmax(self.h_wdra, axis=0)
              optimal_action_wdra = np.empty(sims)
              for k in range(len(idx_wdra)):
                optimal_action_wdra[k] = -self.actions[int(idx_wdra[k])]

              Y = self.discount*V_copy[i,:]
              regression = np.polyfit(X, Y, self.deg)
              continuation_value_hodl = np.polyval(regression, X)
              logger.info(' continuation_hold = {a}'.format(a=continuation_value_hodl))
              
              policy_wdra = np.where((val_wdra >= val_inj) & (val_wdra > continuation_value_hodl))
              policy_inj = np.where(val_inj > continuation_value_hodl)
              policy_hodl = np.where(continuation_value_hodl >= val_inj)
              logger.info(' policies = {a}, {b}, {c}'.format(a=policy_hodl,b=policy_inj,c=policy_wdra))
              self.policy[t,i,policy_wdra] = -1
              self.policy[t,i,policy_inj] = 1
              self.policy[t,i,policy_hodl] = 0
              Value[i,policy_hodl] = Y[policy_hodl]
              Value[i,policy_wdra] = z
              Value[i,policy_inj] = optimal_action_inj[policy_inj]* self.MCprices[t,policy_inj] + self.discount*V_copy[i+1,policy_inj]
              logger.info(' V = {a}'.format(a=Value[i,:]))
            
            elif (i == i_max_prev-1)&(i!=0):
              Y_wdra = self.discount*V_copy[i-1,:]
              logger.info(' Y_withdraw = {a}'.format(a=Y_wdra))
              regression_wdra = np.polyfit(X, Y_wdra, self.deg)
              continuation_value_wdra = np.polyval(regression_wdra, X)
              logger.info(' continuation_withdraw = {a}'.format(a=continuation_value_wdra))
              self.h_wdra[0,:] = -self.actions[0]*self.MCprices[t,:] + continuation_value_wdra
              logger.info(' h_withdraw = {a}'.format(a=self.h_wdra))
              idx_wdra = np.nanargmax(self.h_wdra, axis=0)
              logger.info(' indices_withdraw = {a}'.format(a=idx_wdra))
              val_wdra = np.nanmax(self.h_wdra, axis=0)
              for k in range(len(idx_wdra)):
                optimal_action_wdra[k] = -self.actions[int(idx_wdra[k])]

              continuation_value_inj = infty  
              logger.info(' continuation_inject = {a}'.format(a=continuation_value_inj))
              self.h_inj[2,:] = -self.actions[2]*self.MCprices[t,:] + continuation_value_inj
              idx_inj = np.nanargmax(self.h_inj, axis=0)
              val_inj = np.nanmax(self.h_inj, axis=0)
              optimal_action_inj = np.empty(sims)
              for k in range(len(idx_inj)):
                optimal_action_inj[k] = -self.actions[int(idx_inj[k])]

              Y = self.discount*V_copy[i,:]
              regression = np.polyfit(X, Y, self.deg)
              continuation_value_hodl = np.polyval(regression, X)
              logger.info(' continuation_hold = {a}'.format(a=continuation_value_hodl))
            
              policy_wdra = np.where((val_wdra >= val_inj) & (val_wdra > continuation_value_hodl))
              policy_inj = np.where((val_inj > val_wdra) & (val_inj > continuation_value_hodl))
              policy_hodl = np.where((continuation_value_hodl >= val_inj) & (continuation_value_hodl >= val_wdra))
              logger.info(' policies = {a}, {b}, {c}'.format(a=policy_hodl, b=policy_inj, c=policy_wdra))
              self.policy[t,i,policy_wdra] = -1
              self.policy[t,i,policy_inj] = 1
              self.policy[t,i,policy_hodl] = 0     
              Value[i,policy_hodl] = Y[policy_hodl]
              Value[i,policy_wdra] = optimal_action_wdra[policy_wdra]*self.MCprices[t,policy_wdra] + self.discount*V_copy[i-1,policy_wdra]
              Value[i,policy_inj] = z
              logger.info(' V = {a}'.format(a=Value[i,:]))
            
            elif (i > i_max_prev-1):
              logger.info(' policies = {a}, {b}, {c}'.format(a=np.array([]), b=np.arange(sims), c=np.array([])))
              self.policy[t,i,:] = -1
              Value[i,:] = -self.actions[0]*self.MCprices[t,:] + self.discount*V_copy[i-1,:]
              logger.info(' V = {a}'.format(a=Value[i,:]))
            
            else: 
              Y_wdra = self.discount*V_copy[i-1,:]
              logger.info(' Y_withdraw = {a}'.format(a=Y_wdra))
              regression_wdra = np.polyfit(X, Y_wdra, self.deg)
              continuation_value_wdra = np.polyval(regression_wdra, X)
              logger.info(' continuation_withdraw = {a}'.format(a=continuation_value_wdra))
              self.h_wdra[0,:] = -self.actions[0]*self.MCprices[t,:] + continuation_value_wdra
              logger.info(' h_withdraw = {a}'.format(a=self.h_wdra))
              idx_wdra = np.nanargmax(self.h_wdra, axis=0)
              logger.info(' indices_withdraw = {a}'.format(a=idx_wdra))
              val_wdra = np.nanmax(self.h_wdra, axis=0)
              
              Y_inj = self.discount*V_copy[i+1,:]
              logger.info(' Y_inject = {a}'.format(a=Y_inj))
              regression_inj = np.polyfit(X, Y_inj, self.deg)
              continuation_value_inj = np.polyval(regression_inj, X)
              logger.info(' continuation_inject = {a}'.format(a=continuation_value_inj))
              self.h_inj[2,:] = -self.actions[2]*self.MCprices[t,:] + continuation_value_inj
              logger.info(' h_inject = {a}'.format(a=self.h_inj))
              idx_inj = np.nanargmax(self.h_inj, axis=0)
              logger.info(' indices_inject = {a}'.format(a=idx_inj))
              val_inj = np.nanmax(self.h_inj, axis=0)

              Y = self.discount*V_copy[i,:]
              regression = np.polyfit(X, Y, self.deg)
              continuation_value_hodl = np.polyval(regression, X)
              logger.info(' continuation_hold = {a}'.format(a=continuation_value_hodl))
              optimal_action_wdra = np.empty(sims)
              optimal_action_inj = np.empty(sims)
              
              for k in range(len(idx_wdra)):
                optimal_action_wdra[k] = -self.actions[int(idx_wdra[k])]
              for k in range(len(idx_inj)):
                optimal_action_inj[k] = -self.actions[int(idx_inj[k])]

              policy_wdra = np.where((val_wdra >= val_inj) & (val_wdra > continuation_value_hodl))
              policy_inj = np.where((val_inj > val_wdra) & (val_inj > continuation_value_hodl))
              policy_hodl = np.where((continuation_value_hodl >= val_inj) & (continuation_value_hodl >= val_wdra))
              logger.info(' policies = {a}, {b}, {c}'.format(a=policy_hodl, b=policy_inj, c=policy_wdra))
              self.policy[t,i,policy_wdra] = -1
              self.policy[t,i,policy_inj] = 1
              self.policy[t,i,policy_hodl] = 0
              Value[i,policy_hodl] = Y[policy_hodl]
              Value[i,policy_wdra] = optimal_action_wdra[policy_wdra]*self.MCprices[t,policy_wdra] + self.discount*V_copy[i-1,policy_wdra]
              Value[i,policy_inj] = optimal_action_inj[policy_inj]*self.MCprices[t,policy_inj] + self.discount*V_copy[i+1,policy_inj]
              logger.info(' V = {a}'.format(a=Value[i,:]))
            
          V_copy = np.copy(Value)

        return Value, self.policy[1:,:,:]


    @property
    def price(self):
      V_hat = np.mean(self.value_vector[0], axis=1)
      return self.discount*V_hat[0]

    @property
    def optimalPolicy(self):
      return self.value_vector[1]

    
    def optimalPath(self, scenario):
      Pi = self.optimalPolicy
      Pi = Pi[:,:,scenario]
      policyOptimalPath = np.zeros(Pi.shape[0])
      policyOptimalPath[0] = Pi[0,0]
      pointer = Pi[0,0]
      for t in range(1,Pi.shape[0]):
        policyOptimalPath[t] = Pi[t,int(pointer)]
        pointer += policyOptimalPath[t]
      return policyOptimalPath

    
    def optimalStates(self, scenario):
      Pi = self.optimalPolicy[:,:,scenario]
      I = np.zeros(Pi.shape[0]+1)
      path_opt = self.optimalPath(scenario)
      CF = np.zeros_like(path_opt)
      for t in range(1,Pi.shape[0]):
        I[t] = I[t-1] + path_opt[t-1] * self.DCQ
        CF[t-1] = -self.MCprices[t,scenario] * path_opt[t-1] * self.DCQ
      CF[-1] = -self.MCprices[Pi.shape[0],scenario] * path_opt[-1] * self.DCQ
      return I, CF

# Optimal Pricing/Valuation

df = pd.read_csv('rt_hb_north_paths.csv')
P = df.T.to_numpy()
nsim = P.shape[1]
idx_sim = np.random.randint(0,nsim-1,100).tolist()
P = P[:,idx_sim]
P50 = P.mean(axis=1)
P50 = np.repeat(P50,2).reshape(576,2)

s_mean = StorageLSMC6(5, 1, 576, 0.06, 0.06, 0.59, 100, 0, 10, 2, 5, providedPrice_matrix = P50, logg=None)
s = StorageLSMC6(5, 1, 576, 0.06, 0.06, 0.59, 100, 0, 10, 100, 5, providedPrice_matrix = P, logg=None)

a = s.price; b = s_mean.price; diff= a-b
print('value of LSMC=', diff)
v = s.value_vector[0][0,:]
v_mean = s_mean.value_vector[0][0,:]

opt_st_mean = s_mean.optimalStates(0)
opt_st = s.optimalStates(0)

plt.plot(P)

output_mean = pd.concat([pd.DataFrame(opt_st_mean[0]), pd.DataFrame(opt_st_mean[1])], axis=1)
output_mean.columns = ['inv', 'cash']
output = pd.concat([pd.DataFrame(opt_st[0]), pd.DataFrame(opt_st[1])], axis=1)
output.columns = ['inv', 'cash']

plt.plot(output_mean.iloc[:,0])

P = np.array([[3,3,3,3,3],[3,2.9,2.8,3.1,3.2],[2.9,2.6,3.1,2.7,3.5],[3.4,2.5,3.3,2.9,3.6],[3.1,2.7,3.5,2.4,3.7],[3.2,2.3,3,2,3.9],[2.9,3,3.3,1.8,4]])
plt.plot(P)