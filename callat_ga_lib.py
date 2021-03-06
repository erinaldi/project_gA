import os, sys
import gvar as gv
import scipy.special as spsp
import scipy.stats as stats
import numpy as np
import lsqfit
import matplotlib.pyplot as plt
plt.rc('text', usetex=True)

nature_figs=False
if nature_figs:
    plt.rcParams['text.latex.preamble'] = [
        r'\usepackage{helvet}',
        r'\usepackage{sansmath}',
        r'\sansmath']
    ms = '3'
    cs = 3
    fs_l = 7
    fs_xy = 7
    ts = 7
    lw = 0.5
    gr = 1.618034333
    fs2_base = 3.50394
    fig_size2 = (fs2_base,fs2_base/gr)
    fs3_base = 3.50394 #2.40157
    fig_size3 = (fs3_base,fs3_base/gr)
else:
    ms = '5'
    cs = 2
    fs_l = 12
    fs_xy = 20
    ts = 16
    lw = 1
    gr = 1.618034333
    fs2_base = 7
    fig_size2 = (fs2_base,fs2_base/gr)
    fs3_base = 7 #4.66666667
    fig_size3 = (fs3_base,fs3_base/gr)
plt_axes = [0.14,0.165,0.825,0.825]
n_linspace = 3501
n_linspace = 101

if not os.path.exists('plots'):
    os.makedirs('plots')

ens_abbr = {
    'a15m400' :'l1648f211b580m0217m065m838',
    'a12m400' :'l2464f211b600m0170m0509m635',
    'a09m400' :'l3264f211b630m0124m037m440',
    'a15m350' :'l1648f211b580m0166m065m838',
    'a12m350' :'l2464f211b600m0130m0509m635',
    'a09m350' :'l3264f211b630m00945m037m440',
    'a15m310' :'l1648f211b580m013m065m838',
    'a12m310' :'l2464f211b600m0102m0509m635',
    'a09m310' :'l3296f211b630m0074m037m440',
    'a15m220' :'l2448f211b580m0064m0640m828',
    'a12m220' :'l3264f211b600m00507m0507m628',
    'a12m220S':'l2464f211b600m00507m0507m628',
    'a12m220L':'l4064f211b600m00507m0507m628',
    'a09m220' :'l4896f211b630m00363m0363m430',
    'a15m130' :'l3248f211b580m00235m0647m831',
    'a12m130' :'l4864f211b600m00184m0507m628',
    }

def format_data(switches, gadf, hqdf):
    gar_list = []
    epi_list = []
    aw0_list = []
    afs_list = []
    mpl_list = []
    ed_list  = []
    ens_list = []
    for e in switches['ensembles']:
        ens = ens_abbr[e]
        gar = gadf.query("ensemble=='%s'" %ens).sort_values(by='nbs')['ga'].as_matrix()
        epi = gadf.query("ensemble=='%s'" %ens).sort_values(by='nbs')['epi'].as_matrix()
        mpl = gadf.query("ensemble=='%s' and nbs==0" %ens)['mpil'].as_matrix()[0]
        awm = hqdf.query("ensemble=='%s'" %ens)['aw0_mean'].as_matrix()[0]
        aws = hqdf.query("ensemble=='%s'" %ens)['aw0_sdev'].as_matrix()[0]
        afs = hqdf.query("ensemble=='%s'" %ens)['alfs'].as_matrix()[0]
        ed  = hqdf.query("ensemble=='%s'" %ens)['eps_delta'].as_matrix()[0]
        d = gv.dataset.avg_data({'gar': gar, 'epi':epi}, bstrap=True)
        gar_list.append(d['gar'])
        epi_list.append(d['epi'])
        mpl_list.append(mpl)
        aw0_list.append(gv.gvar(awm,aws))
        ed_list.append(gv.gvar(ed,switches['eps_delta_sig']*ed))
        afs_list.append(afs)
        ens_list.append(e)
    data = {'y':{'gar': gar_list}, 'prior':{'epi': epi_list, 'aw0': aw0_list,'ed':ed_list},
            'x':{'afs': afs_list}, 'mpl': mpl_list, 'ens': ens_list}
    return data

class fit_class():
    def __init__(self,sdict):
        self.ansatz = sdict['ansatz']
        self.n = sdict['truncate']
        self.xsb = sdict['xsb']
        self.alpha = sdict['alpha']
        self.FV = sdict['FV']
        self.FVn = sdict['FVn']
        self.at = '%s_%s' %(sdict['ansatz'],sdict['truncate'])
        # FV Bessel functions
        cn = np.array([6,12,8,6,24,24,0,12,30,24,24,8,24,48,0,6,48,36,24,24]) # |n| multiplicity
        mLn = [i*np.sqrt(np.arange(1,len(cn)+1)) for i in sdict['mL']]
        kn0 = spsp.kn(0, mLn)
        kn1 = spsp.kn(1, mLn)
        self.F1 = np.array([np.sum(cn*kn0[i]-cn*kn1[i]/mLn[i]) for i in range(len(sdict['mL']))])
        self.F3 = -1.5*np.array([np.sum(cn*kn1[i]/mLn[i]) for i in range(len(sdict['mL']))])
        return None
    def get_priors(self,p,data_prior):
        prior = dict(data_prior)
        a = self.ansatz.split('-')[0]
        for k in p[a].keys():
            mean = p[a][k].mean
            sdev = p[a][k].sdev
            if int(k[-1]) <= self.n:
                prior['%s_%s' %(self.at,k)] = gv.gvar(mean,sdev)
            elif int(k[-1]) <= self.FVn and k[0] is 'f':
                prior['%s_%s' %(self.at,k)] = gv.gvar(mean,sdev)
            else: pass
        return prior
    def dfv(self,p):
        epi = p['epi']
        r = 0.
        if self.FVn >= 2:
            g0 = p['%s_g0' %self.at]
            r += 8./3.*epi**2*(g0**3*self.F1+g0*self.F3)
        if self.FVn >= 3:
            f3 = p['%s_f3' %self.at]
            r += f3*epi**3*(self.F1) #+self.F3)
        return r
    def R(self,zz):
        try:
            d = len(zz)
        except:
            d = 0
            zz = [zz]
        r = np.zeros_like(zz)
        for i,z in enumerate(zz):
            if z == 0:
                r[i]  = 0
            elif z > 0. and z < 1.:
                r[i]  = np.sqrt(1-z) * np.log((1-np.sqrt(1-z))/(1+np.sqrt(1-z)))
                r[i] += np.log(4./z)
            elif z == 1:
                r[i]  = np.log(4.)
            elif z > 1.:
                r[i]  = 2*np.sqrt(z-1)*np.arctan(z) + np.log(4./z)
            else:
                print('R(z) only defined for z > 0')
                sys.exit(-1)
        if d == 0:
            r = r[0]
        return r
    def fit_function(self,x,p):
        def nnnlo_analytic_xpt(x,p):
            epi = p['epi']
            aw0 = p['aw0']
            g0 = p['%s_g0' %self.at]
            r = g0 #*np.ones_like(p['epi']) # lo
            if self.n >= 1: # DWF O(a) discretization
                if self.xsb:
                    a1 = p['%s_a1' %self.at]
                    r += a1*aw0
            if self.n >= 2: # nlo
                c2 = p['%s_c2' %self.at]
                a2 = p['%s_a2' %self.at]
                g2  = g0 +2.*g0**3 # nucleon terms
                r += -1.*epi**2 * g2 *np.log(epi**2) # nlo log
                # counter terms
                r += epi**2*c2 # nlo counter term
                r += (aw0**2/(4.*np.pi))*a2 # nlo discretization
                if self.alpha:
                    s2 = p['%s_s2' %self.at]
                    r += x['afs']*(aw0/(4.*np.pi))**2*s2 # nlo alpha_s a^2
                if self.FV:
                    r += self.dfv(p)
            if self.n >= 3: # nnlo
                c3 = p['%s_c3' %self.at]
                r += g0*c3*epi**3 # nnlo log
            if self.n >= 4: # nnnlo analytic terms
                c4 = p['%s_c4' %self.at]
                b4 = p['%s_b4' %self.at]
                a4 = p['%s_a4' %self.at]
                r += epi**4*c4 # nnnlo epi^4
                r += epi**2*(aw0**2/(4.*np.pi))*b4 # nnnlo epi^2 a^2
                r += (aw0**4/(4.*np.pi)**2)*a4 # nnnlo a^4
            return r
        def nnnlo_log2_xpt(x,p):
            r = 0
            if self.n >= 4:
                epi = p['epi']
                g0 = p['%s_g0' %self.at]
                l2 = -16./3*g0 -11./3*g0**3 +16.*g0**5
                l2 += 4.*(2*g0 + 4**g0**3)
                r = l2/4.*epi**4 * (np.log(epi**2))**2
            return r
        def nnnlo_log_xpt(x,p):
            r = 0
            if self.n >= 4:
                epi = p['epi']
                gm4 = p['%s_gm4' %self.at]
                r = gm4*epi**4*np.log(epi**2)
            return r
        def nlo_delta_xpt(x,p):
            r = 0
            if self.n >= 2:
                epi = p['epi']
                ed = p['ed']
                g0 = p['%s_g0' %self.at]
                gnd0 = p['%s_gnd0' %self.at]
                gdd0 = p['%s_gdd0' %self.at]
                g2 = gnd0**2*(2.*g0/9 +50.*gdd0/81) #delta
                r  = -1.*g2*epi**2*np.log(epi**2)
                # extra delta terms
                g2r  = gnd0**2*epi**2 * 32.*g0 / 27
                g2r += gnd0**2*ed**2 * (76.*g0/27 +100.*gdd0/81)
                r   += -1.*g2r*self.R(epi**2 / ed**2)
                g2d  = 76.*g0*gnd0**2 / 27
                g2d += 100.*gdd0*gnd0**2 / 81
                r   += -1.*g2d*ed**2*np.log(4.*ed**2/epi**2)
                # delta mpi^3 term
                r   += 32.*np.pi/27*g0*gnd0**2*epi**3/ed
            return r
        if self.ansatz == 'xpt':
            r = nnnlo_analytic_xpt(x,p)
            return r
        elif self.ansatz == 'xpt-doublelog':
            r = nnnlo_analytic_xpt(x,p)
            r += nnnlo_log2_xpt(x,p)
            return r
        elif self.ansatz == 'xpt-full':
            r = nnnlo_analytic_xpt(x,p)
            r += nnnlo_log2_xpt(x,p)
            r += nnnlo_log_xpt(x,p)
            return r
        elif self.ansatz == 'xpt-delta':
            r = nnnlo_analytic_xpt(x,p)
            r += nlo_delta_xpt(x,p)
            return r
        elif self.ansatz == 'taylor':
            epi = p['epi']
            aw0 = p['aw0']
            c0 = p['%s_c0' %self.at]
            r = c0
            if self.n >= 2:
                c2 = p['%s_c2' %self.at]
                a2 = p['%s_a2' %self.at]
                r += c2*epi**2
                r += a2*(aw0**2/(4.*np.pi))
                if self.FV:
                    r += self.dfv(p)
            if self.n >= 4:
                c4 = p['%s_c4' %self.at]
                b4 = p['%s_b4' %self.at]
                a4 = p['%s_a4' %self.at]
                r += c4*epi**4
                r += a4*(aw0**4/(4.*np.pi)**2)
                r += b4*epi**2*(aw0**2/(4.*np.pi))
            return r
        elif self.ansatz == 'linear':
            epi = p['epi']
            aw0 = p['aw0']
            c0 = p['%s_c0' %self.at]
            r = c0
            if self.n >= 2:
                c2 = p['%s_c2' %self.at]
                a2 = p['%s_a2' %self.at]
                r += c2*epi
                r += a2*(aw0**2/(4.*np.pi))
                if self.FV:
                    r += self.dfv(p)
            if self.n >= 4:
                c4 = p['%s_c4' %self.at]
                a4 = p['%s_a4' %self.at]
                r += c4*epi**2
                r += a4*(aw0**4/(4.*np.pi)**2)
            return r
        elif self.ansatz == 'constant':
            epi = p['epi']
            aw0 = p['aw0']
            c0 = p['%s_c0' %self.at]
            r = c0
            if self.n >= 2:
                a2 = p['%s_a2' %self.at]
                r += a2*(aw0**2/(4.*np.pi))
                if self.FV:
                    r += self.dfv(p)
            if self.n >= 4:
                a4 = p['%s_a4' %self.at]
                r += a4*(aw0**4/(4.*np.pi)**2)
            return r
        else:
            print('need to define fit function')
            raise SystemExit

def fit_data(s,p,data,phys):
    x = data['x']
    y = data['y']['gar']
    result = dict()
    # fit models
    for ansatz_truncate in s['ansatz']['type']:
        sdict = dict(s['ansatz'])
        sdict['ansatz'] = ansatz_truncate.split('_')[0]
        sdict['truncate'] = int(ansatz_truncate.split('_')[1])
        sdict['mL'] = data['mpl']
        fitc = fit_class(sdict)
        prior = fitc.get_priors(p,data['prior'])
        fit = lsqfit.nonlinear_fit(data=(x,y),prior=prior,fcn=fitc.fit_function)
        phys_pt = eval_phys(phys,fitc,fit)
        result[ansatz_truncate] = {'fit':fit, 'phys':phys_pt, 'fitc': fitc}
    return result

def eval_phys(phys,fitc,fit):
    x = {'afs': 0}
    F = phys['fpi']/np.sqrt(2)
    m = phys['mpi']
    epi = m/(4.*np.pi*F)
    ed = phys['Delta']/(4.*np.pi*F)
    priorc = dict()
    for k in fit.p.keys():
        if k == 'epi':
            priorc[k] = epi
        elif k == 'aw0':
            priorc[k] = 0
        elif k == 'ed':
            priorc[k] = np.array(ed)
        else:
            priorc[k] = fit.p[k]
    fitc.FV = False
    phys = fitc.fit_function(x,priorc)
    # get physical point breakdown
    order_contribution = []
    init_order = fitc.n
    if fitc.ansatz in ['taylor','linear']:
        tn = fitc.n//2+1
        order = np.zeros(tn)
        order[0] = 1
        for i in range(1,tn):
            order[i] = 2*i
    else:
        tn = fitc.n
        order = range(1,tn+1)
    for n in range(tn):
        fitc.n = order[n]
        order_contribution.append(fitc.fit_function(x,priorc))
    return {'result': phys, 'priorc': priorc, 'epi': epi, 'order': order_contribution}

def error_budget(s,result_list):
    err = dict()
    for ansatz_truncate in s['ansatz']['type']:
        result = result_list[ansatz_truncate]
        fit = result['fit']
        prior = fit.prior
        priorc = result['phys']['priorc']
        phys = result['phys']['result']
        statistical = phys.partialsdev(fit.y,priorc['epi'],priorc['ed'])
        # compile chiral and discretization and finite volume lists then splat as function input
        X_list = []
        d_list = []
        k_list = []
        v_list = []
        at = ansatz_truncate.split('_')
        ansatz = at[0]
        n = int(at[1])
        for key in prior.keys():
            ks = key.split('_')
            k = ks[-1]
            if k[0] in ['c','g'] and ansatz_truncate in key:
                X_list.append(prior[key])
                k_list.append(key)
            if k[0] in ['a','s','b'] and ansatz_truncate in key:
                d_list.append(prior[key])
                k_list.append(key)
            if s['ansatz']['FVn'] is 3 and k[0] in ['f'] and ansatz_truncate in key:
                v_list.append(prior[key])
                k_list.append(key)
        chiral      = phys.partialsdev(*X_list)
        disc        = phys.partialsdev(*d_list)
        if s['ansatz']['FVn'] is 3:
            fv = phys.partialsdev(*v_list)
        else:
            fv = 0
        pct = {'stat':[statistical/phys.mean*100],'chiral':[chiral/phys.mean*100],'disc':[disc/phys.mean*100],'fv':[fv/phys.mean*100],'total':[phys.sdev/phys.mean*100]}
        std = {'stat':statistical,'chiral':chiral,'disc':disc,'fv':fv,'total':phys.sdev}
        err[ansatz_truncate] = {'pct':pct,'std':std,'mean':phys.mean}
    return err

def bma(switches,result,isospin):
    # read Bayes Factors
    logGBF_list = []
    for a in switches['ansatz']['type']:
        logGBF_list.append(result[a]['fit'].logGBF)
    # initiate a bunch of parameters
    # gA
    gA = 0
    gA_lst = []
    gA_dict = dict()
    # weights
    w_lst = []
    wd = dict()
    # p. dist. fcn
    pdf = 0
    pdfdict = dict()
    # c. dist. fcn.
    cdf = 0
    cdfdict = dict()
    # for plotting
    x = np.linspace(1.222,1.352,13000)
    # error breakdown for each model
    model_error = error_budget(switches,result)
    model_budget = {k:0 for k in model_error[list(model_error.keys())[0]]['std'].keys()}
    for a in switches['ansatz']['type']:
        r = result[a]['phys']['result']
        gA_dict[a] = r
        w = 1/sum(np.exp(np.array(logGBF_list)-result[a]['fit'].logGBF))
        sqrtw = np.sqrt(w) # sqrt scales the std dev correctly
        wd[a] = w
        w_lst.append(w)
        gA += gv.gvar(w*r.mean,sqrtw*r.sdev)
        gA_lst.append(r.mean)
        p = stats.norm.pdf(x,r.mean,r.sdev)
        pdf += w*p
        pdfdict[a] = w*p
        c = stats.norm.cdf(x,r.mean,r.sdev)
        cdf += w*c
        cdfdict[a] = w*c
        # error breakdown
        model_std = model_error[a]['std']
        model_budget = {k:model_budget[k]+w*model_std[k]**2 for k in model_std} # variance breakdown of model average
    gA_lst = np.array(gA_lst)
    w_lst = np.array(w_lst)
    model_var = np.sum(w_lst*gA_lst**2) - gA.mean**2
    final_error = np.sqrt(gA.sdev**2 + isospin**2)
    model_budget['isospin'] = isospin**2
    model_budget['model'] = model_var
    model_budget['total'] = model_budget['total']+model_budget['isospin']+model_budget['model'] # add in quadrature isospin and model variance
    pct_budget = {k:[np.sqrt(model_budget[k])/gA.mean*100] for k in model_budget} # percent breakdown of model average
    error = {'E(gA)': gA.mean, 's(gA)': final_error, 's(Mk)': np.sqrt(model_var), 'weights': wd, 'error_budget': model_budget, 'pct_budget': pct_budget, 'gA_dict':gA_dict}
    plot_params = {'x':x, 'pdf':pdf, 'pdfdict':pdfdict, 'cdf':cdf, 'cdfdict':cdfdict}
    return error, plot_params

class plot_chiral_fit():
    def __init__(self):
        self.loc = './plots'
        self.plot_params = dict()
        self.plot_params['l1648f211b580m0217m065m838']  = {'abbr': 'a15m400',  'color': '#ec5d57', 'marker': 'h', 'label': ''}
        self.plot_params['l1648f211b580m0166m065m838']  = {'abbr': 'a15m350',  'color': '#ec5d57', 'marker': 'p', 'label': ''}
        self.plot_params['l1648f211b580m013m065m838']    = {'abbr': 'a15m310',  'color': '#ec5d57', 'marker': 's', 'label': '$a\simeq 0.15$~fm'}
        self.plot_params['l2448f211b580m0064m0640m828']  = {'abbr': 'a15m220',  'color': '#ec5d57', 'marker': '^', 'label': ''}
        self.plot_params['l3248f211b580m00235m0647m831'] = {'abbr': 'a15m130',  'color': '#ec5d57', 'marker': 'o', 'label': ''}
        self.plot_params['l2464f211b600m0170m0509m635']  = {'abbr': 'a12m400',  'color': '#70bf41', 'marker': 'h', 'label': ''}
        self.plot_params['l2464f211b600m0130m0509m635']  = {'abbr': 'a12m350',  'color': '#70bf41', 'marker': 'p', 'label': ''}
        self.plot_params['l2464f211b600m0102m0509m635']  = {'abbr': 'a12m310',  'color': '#70bf41', 'marker': 's', 'label': '$a\simeq 0.12$~fm'}
        self.plot_params['l2464f211b600m00507m0507m628'] = {'abbr': 'a12m220S', 'color': '#70bf41', 'marker': '^', 'label': ''}
        self.plot_params['l3264f211b600m00507m0507m628'] = {'abbr': 'a12m220',  'color': '#70bf41', 'marker': '^', 'label': ''}
        self.plot_params['l4064f211b600m00507m0507m628'] = {'abbr': 'a12m220L', 'color': '#70bf41', 'marker': '^', 'label': ''}
        self.plot_params['l4864f211b600m00184m0507m628'] = {'abbr': 'a12m130',  'color': '#70bf41', 'marker': 'o', 'label': ''}
        self.plot_params['l3264f211b630m0124m037m440']  = {'abbr': 'a09m400',  'color': '#51a7f9', 'marker': 'h', 'label': ''}
        self.plot_params['l3264f211b630m00945m037m440']  = {'abbr': 'a09m350',  'color': '#51a7f9', 'marker': 'p', 'label': ''}
        self.plot_params['l3296f211b630m0074m037m440']   = {'abbr': 'a09m310',  'color': '#51a7f9', 'marker': 's', 'label': '$a\simeq 0.09$~fm'}
        self.plot_params['l4896f211b630m00363m0363m430'] = {'abbr': 'a09m220',  'color': '#51a7f9', 'marker': '^', 'label': ''}
        self.title = {
            'xpt_4':r'NNLO+ct $\chi$PT','xpt_3':r'NNLO $\chi$PT',
            'xpt_2':r'NLO $\chi$PT',
            'xpt-full_4':r'N3LO $\chi$PT',
            'taylor_2':r'NLO Taylor $\epsilon_\pi^2$','taylor_4':r'NNLO Taylor $\epsilon_\pi^2$',
            'linear_2':r'NLO Taylor $\epsilon_\pi$','linear_4':r'NNLO Taylor $\epsilon_\pi$'
            }
    def plot_chiral(self,s,data,result_list):
        # convergence
        def plot_convergence(result,xp,ansatz):
            fitc = result['fitc']
            init_order = fitc.n
            x = xp['x']
            priorx = xp['priorx']
            #print('CONV FIT:',ansatz)
            if ansatz in ['taylor','linear']:
                tn = int(fitc.n//2+1)
                order = np.zeros(tn)
                order[0] = 1
                for i in range(1,tn):
                    order[i] = 2*i
            else:
                tn = fitc.n
                order = range(1,tn+1)
            ls_list = ['-','--','-.',':']
            label = ['LO','NLO','NNLO','NNLO+ct']
            if ansatz == 'xpt-full':
                label[-1] = 'N3LO'
            phys_converge = []
            for n in range(tn):
                fitc.n = order[n]
                extrap = fitc.fit_function(x,priorx)
                # print numerical breakdown
                converge_prior = dict(priorx)
                converge_prior['epi'] = result['phys']['epi']
                phys_converge.append(fitc.fit_function(x,converge_prior))
                if n == 0:
                    extrap = [extrap for i in range(len(priorx['epi']))]
                mean = np.array([i.mean for i in extrap])
                sdev = np.array([i.sdev for i in extrap])
                ax.fill_between(priorx['epi'],mean+sdev,mean-sdev,\
                    alpha=0.4,label=label[n])
            fitc.n = init_order

            return ax, phys_converge
        # chiral extrapolation
        def c_chiral(ax,result):
            fit = result['fit']
            fitc = result['fitc']
            epi_extrap = np.linspace(0.0001,0.3501,n_linspace)
            aw0_list = [gv.gvar(0.8804,0.003), gv.gvar(0.7036,0.005), gv.gvar(0.5105,0.003)]
            afs_list = [0.58801,0.53796,0.43356]
            pp = self.plot_params
            color_list = [pp['l1648f211b580m013m065m838']['color'], pp['l2464f211b600m0170m0509m635']['color'], pp['l3296f211b630m0074m037m440']['color']]
            label = ['$g_A(\epsilon_\pi,a\simeq 0.15$~fm$)$','$g_A(\epsilon_\pi,a\simeq 0.12$~fm$)$','$g_A(\epsilon_\pi,a\simeq 0.09$~fm$)$']
            fitc.FV = False
            ra = dict()
            for i in range(len(aw0_list)):
                x = {'afs': afs_list[i]}
                priorx = dict()
                for k in fit.p.keys():
                    if k == 'epi':
                        priorx[k] = epi_extrap
                    elif k == 'aw0':
                        priorx[k] = aw0_list[i]
                    else:
                        priorx[k] = fit.p[k]
                extrap = fitc.fit_function(x,priorx)
                ax.plot(epi_extrap,[j.mean for j in extrap],ls='-',marker='',\
                    lw=lw,color=color_list[i],label=label[i])
                ra[i] = extrap
            return ax, ra
        def c_continuum(ax,result):
            fit = result['fit']
            fitc = result['fitc']
            epi_extrap = np.linspace(0.0001,0.3501,n_linspace)
            fitc.FV = False
            x = {'afs': 0}
            priorx = dict()
            for k in fit.p.keys():
                if k == 'epi':
                    priorx[k] = epi_extrap
                elif k == 'aw0':
                    priorx[k] = 0
                else:
                    priorx[k] = fit.p[k]
            extrap = fitc.fit_function(x,priorx)
            mean = np.array([j.mean for j in extrap])
            sdev = np.array([j.sdev for j in extrap])
            epi_phys = result['phys']['epi']
            ax.axvspan(epi_phys.mean-epi_phys.sdev, epi_phys.mean+epi_phys.sdev, alpha=0.4, color='#a6aaa9')
            ax.axvline(epi_phys.mean,ls='--',color='#a6aaa9')
            ax.fill_between(epi_extrap,mean+sdev,mean-sdev,alpha=0.4,color='#b36ae2',label='$g_A^{LQCD}(\epsilon_\pi,a=0)$')
            ax.plot(epi_extrap,mean,ls='--',marker='',lw=lw,color='#b36ae2')
            return ax, {'x':x, 'priorx':priorx}, {'epi':epi_extrap,'y':extrap}
        def c_data(ax,s,result,local_FV_switch=False):
            x = result['fit'].prior['epi']
            if s['ansatz']['FV'] is True or local_FV_switch is True:
                y = result['fit'].y - result['fitc'].dfv(result['fit'].p)
            elif s['ansatz']['FV'] is False or local_FV_switch is False:
                y = result['fit'].y
            datax = []
            datay = []
            elist = []
            for i,ens in enumerate(s['ensembles']):
                e = ens_abbr[ens]
                dx = s['x_shift'][ens]
                ax.errorbar(x=x[i].mean+dx,xerr=x[i].sdev,y=y[i].mean,\
                    yerr=y[i].sdev,ls='None',\
                    marker=self.plot_params[e]['marker'],fillstyle='full',\
                    markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
                    color=self.plot_params[e]['color'],\
                    label=self.plot_params[e]['label'])
                datax.append(x[i])
                datay.append(y[i])
                elist.append(ens)
                # plot FV uncorrected data
                if s['plot']['raw_data']:
                    raw_ga = data['y']['gar'][i]
                    ax.errorbar(x=x[i].mean+dx,y=raw_ga.mean,ls='None',\
                        marker='_',fillstyle='full',markersize=ms,elinewidth=lw,\
                        capsize=cs,color='k',alpha=1)
            return ax, {'x':np.array(x),'y':np.array(y),'ens':np.array(elist)}
        def c_pdg(ax,result):
            gA_pdg = [1.2723, 0.0023]
            ax.errorbar(x=result['phys']['epi'].mean,y=gA_pdg[0],yerr=gA_pdg[1],\
                ls='None',marker='o',fillstyle='none',color='black',\
                markersize=ms,capsize=cs,elinewidth=lw,mew=lw,\
                label='$g_A^{PDG}=1.2723(23)$')
            return ax
        def c_legend(ax):
            handles, labels = ax.get_legend_handles_labels()
            l0_list = ['$g_A^{LQCD}(\epsilon_\pi,a=0)$','$g_A^{PDG}=1.2723(23)$']
            l0 = []
            l1 = []
            for hi,h in enumerate(handles):
                if labels[hi] in l0_list:
                    l0.append(h)
                else:
                    l1.append(h)
            #l0 = [handles[0],handles[-1]]
            #l1 = [handles[i] for i in range(len(handles)-2,0,-1)]
            leg = ax.legend(handles=l0,numpoints=1,loc=1,ncol=1,\
                fontsize=fs_l,edgecolor='k',fancybox=False)
            leg_data = ax.legend(handles=l1,numpoints=1,loc=4,ncol=2,\
                fontsize=fs_l,edgecolor='k',fancybox=False)
            plt.gca().add_artist(leg)
            [ax.spines[key].set_linewidth(lw) for key in ax.spines]
            leg.get_frame().set_linewidth(lw)
            leg_data.get_frame().set_linewidth(lw)

            return None
        ### Chiral extrapolation
        r_chiral = dict()
        r_converge = dict()
        for ansatz_truncate in s['ansatz']['type']:
            if ansatz_truncate.split('_')[0] in ['xpt-delta']:
                print('CAN NOT PRINT: eps_delta(eps_pi) = unknown')
                continue
            result = result_list[ansatz_truncate]
            fig = plt.figure('%s chiral extrapolation' %ansatz_truncate,figsize=fig_size3)
            ax = plt.axes(plt_axes)
            # continuum extrapolation
            ax, xp, r0 = c_continuum(ax,result) # xp is used to make chipt convergence plot
            # plot chiral extrapolation
            ax, ra = c_chiral(ax,result)
            # plot data
            ax, rd = c_data(ax,s,result)
            r_chiral[ansatz_truncate] = {'r0':r0,'ra':ra,'rd':rd}
            # plot pdg
            ax = c_pdg(ax,result)
            # make legend
            c_legend(ax)
            # format plot
            ax.set_ylim([1.075,1.375])
            ax.set_xlim([0,0.32])
            ax.set_xlabel('$\epsilon_\pi=m_\pi/(4\pi F_\pi)$', fontsize=fs_xy)
            ax.set_ylabel('$g_A$', fontsize=fs_xy)
            ax.xaxis.set_tick_params(labelsize=ts,width=lw)
            ax.yaxis.set_tick_params(labelsize=ts,width=lw)
            ax.set_title(self.title[ansatz_truncate],fontdict={'fontsize':fs_xy,'verticalalignment':'top','horizontalalignment':'left'},x=0.05,y=0.9)
            self.ax = ax
            if s['save_figs']:
                plt.savefig('%s/chiral_%s.pdf' %(self.loc,ansatz_truncate),transparent=True)
            plt.draw()
            ### Convergence
            fig = plt.figure('%s chiral convergence' %ansatz_truncate,figsize=fig_size2)
            ax = plt.axes(plt_axes)
            ax, phys_converge = plot_convergence(result,xp,ansatz_truncate.split('_')[0])
            r_converge[ansatz_truncate] = phys_converge
            # plot physical pion point
            epi_phys = result['phys']['epi']
            ax.axvspan(epi_phys.mean-epi_phys.sdev, epi_phys.mean+epi_phys.sdev, alpha=0.4, color='#a6aaa9')
            ax.axvline(epi_phys.mean,ls='--',color='#a6aaa9')
            # make legend
            handles, labels = ax.get_legend_handles_labels()
            leg = ax.legend(handles=handles,loc=3,ncol=2,fontsize=fs_l,\
                edgecolor='k',fancybox=False)
            # format plot
            ax.set_ylim([1.075,1.375])
            ax.set_xlim([0,0.32])
            ax.set_xlabel('$\epsilon_\pi=m_\pi/(4\pi F_\pi)$', fontsize=fs_xy)
            ax.set_ylabel('$g_A$', fontsize=fs_xy)
            ax.xaxis.set_tick_params(labelsize=ts,width=lw)
            ax.yaxis.set_tick_params(labelsize=ts,width=lw)
            ax.set_title(self.title[ansatz_truncate],fontdict={'fontsize':fs_xy,'verticalalignment':'top','horizontalalignment':'left'},x=0.05,y=0.9)
            [ax.spines[key].set_linewidth(lw) for key in ax.spines]
            leg.get_frame().set_linewidth(lw)

            if s['save_figs']:
                plt.savefig('%s/convergence_%s.pdf' %(self.loc,ansatz_truncate),transparent=True)
            plt.draw()
        return r_chiral, r_converge
    def plot_continuum(self,s,data,result_list):
        def a_chiral(ax,result):
            fit = result['fit']
            fitc = result['fitc']
            epi_list = [0.1135, 0.182, 0.248, 0.2714, 0.29828]
            aw0_extrap = np.linspace(0.0,0.9001,9101)
            epi = 0
            c15 = self.plot_params['l1648f211b580m013m065m838']['color']
            c12 = self.plot_params['l2464f211b600m0170m0509m635']['color']
            c09 = self.plot_params['l3296f211b630m0074m037m440']['color']
            ls_list = ['-','--','-.',':','-']
            label = ['$g_A(\epsilon^{(130)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(220)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(310)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(350)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(400)}_\pi,\epsilon_a)$']
            color = ['black','black','black','black','black']
            dashes = [8, 4, 2, 4, 2, 4]
            fitc.FV = False
            rm = dict()
            for i in range(len(epi_list)):
                x = {'afs': 0}
                priorx = dict()
                for k in fit.p.keys():
                    if k == 'aw0':
                        priorx[k] = aw0_extrap
                    elif k == 'epi':
                        priorx[k] = epi_list[i]
                    else:
                        priorx[k] = fit.p[k]
                extrap = fitc.fit_function(x,priorx)
                aw0_extrap_plot = aw0_extrap**2/(4*np.pi)
                if i == 4:
                    ax.plot(aw0_extrap_plot,[j.mean for j in extrap],\
                        ls=ls_list[i],dashes=dashes,marker='',lw=lw,\
                        color=color[i],label=label[i])
                else:
                    ax.plot(aw0_extrap_plot,[j.mean for j in extrap],\
                        ls=ls_list[i],marker='',lw=lw,\
                        color=color[i],label=label[i])
                rm[i] = extrap
            return ax, rm
        def a_cont(ax,result):
            fit = result['fit']
            fitc = result['fitc']
            epi_phys = result['phys']['epi']
            aw0_extrap = np.linspace(0.0,0.9001,9101)
            fitc.FV = False
            x = {'afs': 0}
            priorx = dict()
            for k in fit.p.keys():
                if k == 'epi':
                    priorx[k] = epi_phys
                elif k == 'aw0':
                    priorx[k] = aw0_extrap
                else:
                    priorx[k] = fit.p[k]
            extrap = fitc.fit_function(x,priorx)
            mean = np.array([j.mean for j in extrap])
            sdev = np.array([j.sdev for j in extrap])
            aw0_extrap_plot = aw0_extrap**2/(4*np.pi)
            ax.fill_between(aw0_extrap_plot,mean+sdev,mean-sdev,alpha=0.4,color='#b36ae2',label='$g_A^{LQCD}(\epsilon_\pi^{phys.},\epsilon_a)$')
            ax.plot(aw0_extrap_plot,mean,ls='-',marker='',lw=lw,color='#b36ae2')
            return ax, {'x':x, 'priorx':priorx}, {'aw0_extrap_plot':aw0_extrap_plot,'y':extrap}
        def a_data(ax,s,result):
            x = result['fit'].prior['aw0']
            if s['ansatz']['FV']:
                y = result['fit'].y - result['fitc'].dfv(result['fit'].p)
            else:
                y = result['fit'].y
            xlist = []
            ylist = []
            elist = []
            for i,ens in enumerate(s['ensembles']):
                e = ens_abbr[ens]
                xplot = x[i]**2/(4.*np.pi)
                ax.errorbar(x=xplot.mean,xerr=xplot.sdev,y=y[i].mean,yerr=y[i].sdev,\
                    marker=self.plot_params[e]['marker'],ls='None',fillstyle='full',\
                    markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
                    color=self.plot_params[e]['color'])
                xlist.append(xplot)
                ylist.append(y[i])
                elist.append(e)
            return ax, {'x':np.array(xlist),'y':np.array(ylist),'ens':np.array(elist)}
        def a_pdg(ax,result):
            gA_pdg = [1.2723, 0.0023]
            ax.errorbar(x=0,y=gA_pdg[0],yerr=gA_pdg[1],ls='None',marker='o',\
                fillstyle='none',markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
                color='black',label='$g_A^{PDG}=1.2723(23)$')
            return ax
        def a_legend(ax):
            handles, labels = ax.get_legend_handles_labels()
            l0_list = ['$g_A^{LQCD}(\epsilon_\pi^{phys.},\epsilon_a)$',\
                '$g_A^{PDG}=1.2723(23)$']
            l0 = []
            l1 = []
            for hi,h in enumerate(handles):
                if labels[hi] in l0_list:
                    l0.append(h)
                else:
                    l1.append(h)
            leg = ax.legend(handles=l0,numpoints=1,loc=1,ncol=1,\
                fontsize=fs_l,edgecolor='k',fancybox=False)
            leg_data = ax.legend(handles=l1,numpoints=1,loc=3,ncol=2,\
                fontsize=fs_l,edgecolor='k',fancybox=False)
            plt.gca().add_artist(leg)
            leg.get_frame().set_linewidth(lw)
            leg_data.get_frame().set_linewidth(lw)
            return None
        r_cont = dict()
        for ansatz_truncate in s['ansatz']['type']:
            if ansatz_truncate.split('_')[0] in ['xpt-delta']:
                print('CAN NOT PRINT: eps_delta(eps_pi) = unknown')
                continue
            result = result_list[ansatz_truncate]
            fig = plt.figure('%s continuum extrapolation' %ansatz_truncate,figsize=fig_size2)
            ax = plt.axes(plt_axes)
            # continuum extrapolation
            ax, res, r0 = a_cont(ax,result)
            # chiral extrapolation
            ax, rm = a_chiral(ax,result)
            # plot data
            ax, rd = a_data(ax,s,result)
            r_cont[ansatz_truncate] = {'r0':r0,'rm':rm,'rd':rd}
            # plot PDG
            ax = a_pdg(ax,result)
            # make legend
            a_legend(ax)
            # format plot
            ax.set_ylim([1.075,1.375])
            ax.set_xlim([-0.001,0.81/(4*np.pi)])
            ax.set_xlabel('$\epsilon_a^2=a^2/(4\pi w^2_0)$', fontsize=fs_xy)
            ax.set_ylabel('$g_A$', fontsize=fs_xy)
            ax.xaxis.set_tick_params(labelsize=ts,width=lw)
            ax.yaxis.set_tick_params(labelsize=ts,width=lw)
            ax.set_title(self.title[ansatz_truncate],fontdict={'fontsize':fs_xy,'verticalalignment':'top','horizontalalignment':'left'},x=0.05,y=0.9)
            [ax.spines[key].set_linewidth(lw) for key in ax.spines]
            if s['save_figs']:
                plt.savefig('%s/continuum_%s.pdf' %(self.loc,ansatz_truncate),transparent=True)
            plt.draw()
        return r_cont
    def plot_volume(self,s,data,result_list):
        if s['ansatz']['FV']:
            def v_vol(ax,s,result,ansatz_truncate):
                fit = result['fit']
                mpiL_extrap = np.linspace(3,10,500)
                sdict = dict(s['ansatz'])
                sdict['ansatz'] = ansatz_truncate.split('_')[0]
                sdict['truncate'] = int(ansatz_truncate.split('_')[1])
                sdict['mL'] = mpiL_extrap
                fitc = fit_class(sdict)
                x = {'afs': 0}
                priorx = dict()
                for k in fit.p.keys():
                    if k == 'epi':
                        priorx[k] = gv.gvar(0.18220,0.00044)
                    elif k == 'aw0':
                        priorx[k] = gv.gvar(0.7036,0.0005)
                    else:
                        priorx[k] = fit.p[k]
                extrap = fitc.fit_function(x,priorx)
                mean = np.array([j.mean for j in extrap])
                sdev = np.array([j.sdev for j in extrap])
                mpiL_extrap_plot = np.exp(-mpiL_extrap)/np.sqrt(mpiL_extrap)
                ax.fill_between(mpiL_extrap_plot,mean+sdev,mean-sdev,alpha=0.4,color='#70bf41')
                if s['ansatz']['FVn'] == 3:
                    lbl = 'NNLO $\chi$PT estimate'
                elif s['ansatz']['FVn'] == 2:
                    lbl = 'NLO $\chi$PT prediction'
                ax.plot(mpiL_extrap_plot,mean,ls='--',marker='',lw=lw,\
                    color='#70bf41',label=lbl)
                return ax, {'mpiL_extrap_plot':mpiL_extrap_plot,'y':extrap}
            def v_data(ax,s,data,result):
                x = data['mpl']
                y = result['fit'].y
                xlist = []
                ylist = []
                elist = []
                for i,ens in enumerate(s['ensembles']):
                    e = ens_abbr[ens]
                    if ens in ['a12m220S','a12m220','a12m220L']:
                        xplot = np.exp(-x[i])/np.sqrt(x[i])
                        ax.errorbar(x=xplot,y=y[i].mean,yerr=y[i].sdev,ls='None',\
                            marker=self.plot_params[e]['marker'],fillstyle='full',\
                            markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
                            color=self.plot_params[e]['color'],\
                            label=self.plot_params[e]['label'])
                        xlist.append(xplot)
                        ylist.append(y[i])
                        elist.append(e)
                    else: pass
                return ax, {'x':np.array(xlist),'y':np.array(ylist),'ens':np.array(elist)}
            def v_legend(ax):
                handles, labels = ax.get_legend_handles_labels()
                leg = ax.legend(handles=handles,loc=4,ncol=1, fontsize=fs_l,edgecolor='k',fancybox=False)
                plt.gca().add_artist(leg)
                leg.get_frame().set_linewidth(lw)
                return None
            r_fv = dict()
            for ansatz_truncate in s['ansatz']['type']:
                if ansatz_truncate.split('_')[0] in ['xpt-delta']:
                    print('CAN NOT PRINT: eps_delta(eps_pi) = unknown')
                    continue
                result = result_list[ansatz_truncate]
                fig = plt.figure('%s infinite volume extrapolation' %ansatz_truncate,figsize=fig_size2)
                ax = plt.axes(plt_axes)
                # plot IV extrapolation
                ax, r0 = v_vol(ax,s,result,ansatz_truncate)
                # plot data
                ax, rd = v_data(ax,s,data,result)
                r_fv[ansatz_truncate] = {'r0':r0,'rd':rd}
                # plot legend
                v_legend(ax)
                # format plot
                ax.set_ylim([1.22,1.3])
                ax.set_xlim([0,0.025])
                ax.set_xlabel('$e^{-m_\pi L}/(m_\pi L)^{1/2}$', fontsize=fs_xy)
                ax.set_ylabel('$g_A$', fontsize=fs_xy)
                ax.yaxis.set_ticks([1.23,1.25,1.27,1.29])
                ax.xaxis.set_tick_params(labelsize=ts,width=lw)
                ax.yaxis.set_tick_params(labelsize=ts,width=lw)
                ax.set_title(self.title[ansatz_truncate],fontdict={'fontsize':fs_xy,'verticalalignment':'top','horizontalalignment':'left'},x=0.05,y=0.9)
                [ax.spines[key].set_linewidth(lw) for key in ax.spines]
                if s['save_figs']:
                    plt.savefig('%s/volume_%s.pdf' %(self.loc,ansatz_truncate),transparent=True)
                plt.draw()
            return r_fv
        else:
            print('no FV prediction')
    def plot_histogram(self,s,pp):
        x = pp['x']
        ysum = pp['pdf']
        ydict = pp['pdfdict']
        cdf = pp['cdf']
        # '-','--','-.',':'
        # #ec5d57 #70bf41 #51a7f9
        p = dict()
        p['taylor_2']    = {'color':'#ec5d57','ls':'--','tag':'NLO Taylor $\epsilon_\pi^2$'}
        p['taylor_4']    = {'color':'#ec5d57','ls':':','tag':'NNLO Taylor $\epsilon_\pi^2$'}
        p['xpt_3']       = {'color':'#70bf41','ls':'--','tag':'NNLO $\chi$PT'}
        p['xpt_4']       = {'color':'#70bf41','ls':':','tag':'NNLO+ct $\chi$PT'}
        p['xpt-full_4']  = {'color':'#70bf41','ls':'-','tag':'N3LO $\chi$PT'}
        p['linear_2']    = {'color':'#51a7f9','ls':'--','tag':'NLO Taylor $\epsilon_\pi$'}
        p['linear_4']    = {'color':'#51a7f9','ls':':','tag':'NNLO Taylor $\epsilon_\pi$'}
        p['xpt-delta_2'] = {'color':'#70bf41','ls':'--','tag':'NLO $\Delta\chi$PT'}
        p['xpt-delta_3'] = {'color':'#70bf41','ls':':','tag':'NNLO $\Delta\chi$PT'}
        p['xpt-delta_4'] = {'color':'#70bf41','ls':'-.','tag':'NNLO+ct $\Delta\chi$PT'}
        fig = plt.figure('result histogram',figsize=fig_size2)
        ax = plt.axes(plt_axes)
        ax.fill_between(x=x,y1=ysum,facecolor='#b36ae2',edgecolor='black',alpha=0.4,label='model average')
        # get 95% confidence
        lidx95 = abs(cdf-0.025).argmin()
        uidx95 = abs(cdf-0.975).argmin()
        ax.fill_between(x=x[lidx95:uidx95],y1=ysum[lidx95:uidx95],facecolor='#b36ae2',edgecolor='black',alpha=0.4)
        # get 68% confidence
        lidx68 = abs(cdf-0.158655254).argmin()
        uidx68 = abs(cdf-0.841344746).argmin()
        ax.fill_between(x=x[lidx68:uidx68],y1=ysum[lidx68:uidx68],facecolor='#b36ae2',edgecolor='black',alpha=0.4)
        # plot black curve over
        ax.errorbar(x=[x[lidx95],x[lidx95]],y=[0,ysum[lidx95]],color='black',lw=lw)
        ax.errorbar(x=[x[uidx95],x[uidx95]],y=[0,ysum[uidx95]],color='black',lw=lw)
        ax.errorbar(x=[x[lidx68],x[lidx68]],y=[0,ysum[lidx68]],color='black',lw=lw)
        ax.errorbar(x=[x[uidx68],x[uidx68]],y=[0,ysum[uidx68]],color='black',lw=lw)
        ax.errorbar(x=x,y=ysum,ls='-',color='black',lw=lw)
        for a in ydict.keys():
            ax.plot(x,ydict[a],ls=p[a]['ls'],color=p[a]['color'],lw=lw,\
                label=p[a]['tag'])
        leg = ax.legend(fontsize=fs_l,edgecolor='k',fancybox=False)
        ax.set_ylim(bottom=0)
        ax.set_xlim([1.225,1.335])
        ax.set_xlabel('$g_A$', fontsize=fs_xy)
        frame = plt.gca()
        frame.axes.get_yaxis().set_visible(False)
        ax.xaxis.set_tick_params(labelsize=ts,width=lw)
        # legend line width
        [ax.spines[key].set_linewidth(lw) for key in ax.spines]
        leg.get_frame().set_linewidth(lw)

        if s['save_figs']:
            plt.savefig('%s/model_avg_histogram.pdf' %(self.loc),transparent=True)
        plt.draw()
    def model_avg_chiral(self,s,phys,wd,r_chiral,data=None):
        # model average
        y = 0
        ya = {0:0,1:0,2:0}
        d = 0
        for k in wd.keys():
            if k.split('_')[0] in ['xpt-delta']:
                print('CAN NOT PRINT: eps_delta(eps_pi) = unknown')
                continue
            y += wd[k]*r_chiral[k]['r0']['y']
            d += wd[k]*r_chiral[k]['rd']['y']
            for a in r_chiral[k]['ra'].keys():
                ya[a] += wd[k]*r_chiral[k]['ra'][a]
        # plot
        fig = plt.figure('model average chiral extrapolation',figsize=fig_size2)
        ax = plt.axes(plt_axes)
        # physical epi
        F = phys['fpi']/np.sqrt(2)
        m = phys['mpi']
        epi_phys = m/(4.*np.pi*F)
        ax.axvspan(epi_phys.mean-epi_phys.sdev, epi_phys.mean+epi_phys.sdev, alpha=0.4, color='#a6aaa9')
        ax.axvline(epi_phys.mean,ls='--',color='#a6aaa9')
        # finite lattice spacing
        pp = self.plot_params
        color_list = [pp['l1648f211b580m013m065m838']['color'], pp['l2464f211b600m0170m0509m635']['color'], pp['l3296f211b630m0074m037m440']['color']]
        label = ['$g_A(\epsilon_\pi,a\simeq 0.15$~fm$)$','$g_A(\epsilon_\pi,a\simeq 0.12$~fm$)$','$g_A(\epsilon_\pi,a\simeq 0.09$~fm$)$']
        for idx,i in enumerate(r_chiral[k]['ra'].keys()):
            #print(i)
            #ax.errorbar(x=r_chiral[k]['r0']['epi'],y=[j.mean for j in ya[i]],ls='-',\
            #    marker='',mew=lw,color=color_list[idx],label=label[idx])
            ax.plot(r_chiral[k]['r0']['epi'],[j.mean for j in ya[i]],\
                linewidth=lw,color=color_list[idx],label=label[idx])
        # data
        for i,ens in enumerate(r_chiral[k]['rd']['ens']):
            e = ens_abbr[ens]
            dx = s['x_shift'][ens]
            ax.errorbar(x=r_chiral[k]['rd']['x'][i].mean+dx,y=d[i].mean,yerr=d[i].sdev,\
                ls='None',marker=self.plot_params[e]['marker'],fillstyle='full',\
                markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
                color=self.plot_params[e]['color'],label=self.plot_params[e]['label'])
        # plot FV uncorrected data
        if s['plot']['raw_data']:
            for idx,ens in enumerate(data['ens']):
                dx = s['x_shift'][ens]
                raw_epi = data['prior']['epi'][idx]
                raw_ga = data['y']['gar'][idx]
                #ax.errorbar(x=raw_epi.mean+dx,y=raw_ga.mean,yerr=raw_ga.sdev,ls='None',marker=self.plot_params[ens_abbr[ens]]['marker'],fillstyle='none',markersize=ms,elinewidth=lw,capsize=cs,color=self.plot_params[ens_abbr[ens]]['color'],alpha=0.4)
                ax.errorbar(x=raw_epi.mean+dx,y=raw_ga.mean,ls='None',marker='_',fillstyle='full',markersize=ms,elinewidth=lw,capsize=cs,color='k',alpha=1)
        # pdg
        gA_pdg = [1.2723, 0.0023]
        ax.errorbar(x=epi_phys.mean,y=gA_pdg[0],yerr=gA_pdg[1],ls='None',marker='o',\
            fillstyle='none',markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
            color='black',label='$g_A^{PDG}=1.2723(23)$')
        # continuum extrap
        epi_extrap = r_chiral[k]['r0']['epi']
        mean = np.array([i.mean for i in y])
        sdev = np.array([i.sdev for i in y])
        ax.fill_between(epi_extrap,mean+sdev,mean-sdev,alpha=0.4,color='#b36ae2',label='$g_A^{LQCD}(\epsilon_\pi,a=0)$')
        #ax.errorbar(x=epi_extrap,y=mean,ls='--',marker='',mew=lw,\
        #    color='#b36ae2')
        ax.plot(epi_extrap,mean,ls='--',linewidth=lw,color='#b36ae2')
        # legend
        l0_list = ['$g_A^{LQCD}(\epsilon_\pi,a=0)$','$g_A^{PDG}=1.2723(23)$']
        l0 = []
        l1 = []
        handles, labels = ax.get_legend_handles_labels()
        for hi,h in enumerate(handles):
            if labels[hi] in l0_list:
                l0.append(h)
            else:
                l1.append(h)
        #l0 = [handles[0],handles[-1]]
        #l1 = [handles[i] for i in range(len(handles)-2,0,-1)]
        leg = ax.legend(handles=l0,numpoints=1,loc=1,ncol=1,fontsize=fs_l,\
            edgecolor='k',fancybox=False)
        leg_data = ax.legend(handles=l1,numpoints=1,loc=4,ncol=2,fontsize=fs_l,\
            edgecolor='k',fancybox=False)
        plt.gca().add_artist(leg)
        # settings
        ax.set_ylim([1.075,1.375])
        ax.set_xlim([0,0.32])
        ax.set_xlabel('$\epsilon_\pi=m_\pi/(4\pi F_\pi)$', fontsize=fs_xy)
        ax.set_ylabel('$g_A$', fontsize=fs_xy)
        ax.xaxis.set_tick_params(labelsize=ts,width=lw)
        ax.yaxis.set_tick_params(labelsize=ts,width=lw)
        ax.set_title('model average',fontdict={'fontsize':fs_xy,'verticalalignment':'top','horizontalalignment':'left'},x=0.05,y=0.9)
        [ax.spines[key].set_linewidth(lw) for key in ax.spines]
        leg.get_frame().set_linewidth(lw)
        leg_data.get_frame().set_linewidth(lw)
        #lleg = plt.gca().get_legend()
        #llines = lleg.get_lines()
        #plt.setp(llines, linewidth=lw)
        if s['save_figs']:
            plt.savefig('%s/chiral_modelavg.pdf' %(self.loc),transparent=True)
        plt.draw()
    def model_avg_cont(self,s,wd,r_cont):
        # model average
        y = 0
        ym = {0:0,1:0,2:0,3:0,4:0}
        d = 0
        for k in wd.keys():
            y += wd[k]*r_cont[k]['r0']['y']
            d += wd[k]*r_cont[k]['rd']['y']
            for a in r_cont[k]['rm'].keys():
                ym[a] += wd[k]*r_cont[k]['rm'][a]
        # plot
        fig = plt.figure('model average chiral extrapolation',figsize=fig_size2)
        ax = plt.axes(plt_axes)
        # physical pion mass extrap
        a_extrap = r_cont[k]['r0']['aw0_extrap_plot']
        mean = np.array([i.mean for i in y])
        sdev = np.array([i.sdev for i in y])
        ax.fill_between(a_extrap,mean+sdev,mean-sdev,alpha=0.4,color='#b36ae2',label='$g_A^{LQCD}(\epsilon_\pi^{phys.},\epsilon_a)$')
        ax.plot(a_extrap,mean,ls='--',marker='',linewidth=lw,color='#b36ae2')
        # unphysical pion masses
        ls_list = ['-','--','-.',':','-']
        label = ['$g_A(\epsilon^{(130)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(220)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(310)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(350)}_\pi,\epsilon_a)$','$g_A(\epsilon^{(400)}_\pi,\epsilon_a)$']
        color = ['black','black','black','black','black']
        dashes = [8, 4, 2, 4, 2, 4]
        for idx,i in enumerate(r_cont[k]['rm'].keys()):
            if i == 4:
                ax.plot(a_extrap,[j.mean for j in ym[i]],ls=ls_list[idx],\
                    dashes=dashes,marker='',linewidth=lw,color=color[idx],\
                    label=label[idx])
            else:
                ax.plot(a_extrap,[j.mean for j in ym[i]],ls=ls_list[idx],\
                    marker='',linewidth=lw,color=color[idx],label=label[idx])
        # data
        for i,e in enumerate(r_cont[k]['rd']['ens']):
            ax.errorbar(x=r_cont[k]['rd']['x'][i].mean,y=d[i].mean,yerr=d[i].sdev,\
                ls='None',marker=self.plot_params[e]['marker'],fillstyle='full',\
                markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
                color=self.plot_params[e]['color'])
        # pdg
        gA_pdg = [1.2723, 0.0023]
        #ax.errorbar(x=0,y=gA_pdg[0],yerr=gA_pdg[1],ls='None',marker='o',fillstyle='none',markersize=ms,capsize=cs,color='black',label='$g_A^{PDG}=1.2723(23)$')
        ax.errorbar(x=0,y=gA_pdg[0],yerr=gA_pdg[1],ls='None',marker='o',\
            fillstyle='none',markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
            color='black',label='$g_A^{PDG}=1.2723(23)$')
        # legend
        #handles, labels = ax.get_legend_handles_labels()
        #l0 = [handles[0],handles[-1]]
        #l1 = [handles[i] for i in range(len(handles)-2,0,-1)]
        l0_list = ['$g_A^{LQCD}(\epsilon_\pi^{phys.},\epsilon_a)$',\
            '$g_A^{PDG}=1.2723(23)$']
        l0 = []
        l1 = []
        handles, labels = ax.get_legend_handles_labels()
        for hi,h in enumerate(handles):
            if labels[hi] in l0_list:
                l0.append(h)
            else:
                l1.append(h)
        leg = ax.legend(handles=l0,numpoints=1,loc=1,ncol=1,fontsize=fs_l,\
            edgecolor='k',fancybox=False)
        leg_data = ax.legend(handles=l1,numpoints=1,loc=3,ncol=2,fontsize=fs_l,\
            edgecolor='k',fancybox=False)
        plt.gca().add_artist(leg)
        # settings
        ax.set_ylim([1.075,1.375])
        ax.set_xlim([-0.001,0.81/(4*np.pi)])
        ax.set_xlabel('$\epsilon_a^2=a^2/(4\pi w^2_0)$', fontsize=fs_xy)
        ax.set_ylabel('$g_A$', fontsize=fs_xy)
        ax.xaxis.set_tick_params(labelsize=ts,width=lw)
        ax.yaxis.set_tick_params(labelsize=ts,width=lw)
        ax.set_title('model average',fontdict={'fontsize':fs_xy,\
            'verticalalignment':'top','horizontalalignment':'left'},x=0.05,y=0.9)
        [ax.spines[key].set_linewidth(lw) for key in ax.spines]
        leg.get_frame().set_linewidth(lw)
        leg_data.get_frame().set_linewidth(lw)
        #plt.setp(plt.gca().get_legend().get_lines(),linewidth=lw)
        #plt.gca().get_legend().get_frame().set_linewidth(lw)
        #lleg = plt.gca().get_legend()
        #llines = lleg.get_lines()
        #plt.setp(llines, linewidth=lw)

        if s['save_figs']:
            plt.savefig('%s/cont_modelavg.pdf' %(self.loc),transparent=True)
        plt.draw()
    def model_avg_fv(self,s,wd,r_fv):
        # model average
        y = 0
        ym = {0:0,1:0,2:0,3:0,4:0}
        d = 0
        for k in wd.keys():
            y += wd[k]*r_fv[k]['r0']['y']
            d += wd[k]*r_fv[k]['rd']['y']
        # plot
        fig = plt.figure('model average volume extrapolation',figsize=fig_size2)
        ax = plt.axes(plt_axes)
        # infinite volume extrapolation
        l_extrap = r_fv[k]['r0']['mpiL_extrap_plot']
        mean = np.array([i.mean for i in y])
        sdev = np.array([i.sdev for i in y])
        ax.fill_between(l_extrap,mean+sdev,mean-sdev,alpha=0.4,color='#70bf41')
        if s['ansatz']['FVn'] == 3:
            lbl = 'NNLO $\chi$PT estimate'
        elif s['ansatz']['FVn'] == 2:
            lbl = 'NLO $\chi$PT prediction'
        ax.plot(l_extrap,mean,ls='--',marker='',linewidth=lw,color='#70bf41',label=lbl)
        # data
        for i,e in enumerate(r_fv[k]['rd']['ens']):
            ax.errorbar(x=r_fv[k]['rd']['x'][i],y=d[i].mean,yerr=d[i].sdev,\
                ls='None',marker=self.plot_params[e]['marker'],fillstyle='full',\
                markersize=ms,elinewidth=lw,capsize=cs,mew=lw,\
                color=self.plot_params[e]['color'])
        # legend
        handles, labels = ax.get_legend_handles_labels()
        leg = ax.legend(handles=handles,loc=4,ncol=1, fontsize=fs_l,edgecolor='k',fancybox=False)
        plt.gca().add_artist(leg)
        # settings
        ax.set_ylim([1.22,1.3])
        ax.set_xlim([0,0.025])
        ax.set_xlabel('$e^{-m_\pi L}/(m_\pi L)^{1/2}$', fontsize=fs_xy)
        ax.set_ylabel('$g_A$', fontsize=fs_xy)
        ax.yaxis.set_ticks([1.23,1.25,1.27,1.29])
        ax.xaxis.set_tick_params(labelsize=ts,width=lw)
        ax.yaxis.set_tick_params(labelsize=ts,width=lw)
        ax.set_title('model average',fontdict={'fontsize':fs_xy,'verticalalignment':'top','horizontalalignment':'left'},x=0.05,y=0.9)
        [ax.spines[key].set_linewidth(lw) for key in ax.spines]
        leg.get_frame().set_linewidth(lw)

        if s['save_figs']:
            plt.savefig('%s/fv_modelavg.pdf' %(self.loc),transparent=True)
        plt.draw()

def mpi_corr(s,phys,r,w_me):
    epi_mpi = {'m130':0.11347,'m220':0.18156,'m310':0.24485,\
        'm350':0.27063,'m400':0.29841}
    epi_all = [(phys['mpi']/2/np.sqrt(2)/np.pi/phys['fpi']).mean]
    for m in ['m130','m220','m310','m350','m400']:
        if any(m in ms for ms in s['ensembles']):
            epi_all.append(epi_mpi[m])
    dcorr = dict()
    for a in r:
        fit = r[a]['fit']
        fitc = r[a]['fitc']
        fitc.FV = False
        x = {'afs': 0}
        priorx = dict()
        for k in fit.p.keys():
            if k == 'epi':
                priorx[k] = np.array(epi_all)
            elif k == 'aw0':
                priorx[k] = 0
            else:
                priorx[k] = fit.p[k]
        extrap = fitc.fit_function(x,priorx)
        #print(extrap)
        y = dict()
        y['corr'] = gv.evalcorr(extrap)
        y['eyx'] = extrap[0].sdev*y['corr'][1,:]
        dcorr[a] = y
    print('Correlation')
    print('e_pi')
    print(['%.5f' %e for e in epi_all])
    for a in r:
        string = a
        for i,ri in enumerate(dcorr[a]['corr'][0,:]):
            string += ' & %.4f ' %ri
        print(string)
    print('\ndelta_gA(mpi_phys,mpi)[%]')
    print('e_pi')
    print(['%.5f' %e for e in epi_all[1:]])
    wi = []
    dg = []
    avg = []
    fits = []
    for a in r:
        fits.append(a)
        wi.append(w_me['weights'][a])
        dg.append(dcorr[a]['eyx'][1:]/r[a]['phys']['result'].mean)
        avg.append(r[a]['phys']['result'].mean)
        string = a
        s2 = a
        for i,ri in enumerate(dcorr[a]['eyx'][1:]):
            string += ' & %.4f ' %ri # shift
            s2 += ' & %.2f ' %(dg[-1][i]*100) # %shift vs mean
            # 20 January 2018, verified percent matches shift -Andre
        #print(string)
        print(s2)
    dg = np.array(dg)
    wi = np.array(wi)
    avg = np.array(avg)
    string = 'model avg'
    for i in range(len(epi_all)-1):
        string += ' & %.2f' %(np.sum(wi*dg[:,i]*avg/w_me['E(gA)'])*100)
        # taking the weigthed avg of dg is same as weighted avg of shift
    print(string)

if __name__=='__main__':
    print("chipt library")
