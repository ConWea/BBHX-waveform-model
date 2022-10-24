import functools

@functools.lru_cache()
def get_waveform_genner(mf_min, run_phenomd=True):
    from bbhx.waveformbuild import BBHWaveformFD

    wave_gen = BBHWaveformFD(amp_phase_kwargs=dict(run_phenomd=run_phenomd, mf_min=mf_min))
    return wave_gen

def bbhx_fd(ifos=None, run_phenomd=True, nyquist_freq=0.1,
            ref_frame='LISA', sample_points=None, **params):

    if ifos is None:
        raise Exception("Must define data streams to compute")

    import numpy as np
    from scipy.interpolate import interp1d
    from pycbc.types import FrequencySeries, Array
    from pycbc import pnutils
    from bbhx.utils.transform import LISA_to_SSB
    from bbhx.waveforms.phenomhm import PhenomHMAmpPhase

    m1 = params['mass1']
    m2 = params['mass2']
    a1 = params['spin1z']
    a2 = params['spin2z']
    dist = pnutils.megaparsecs_to_meters(params['distance'])
    phi_ref = params['coa_phase']
    f_ref = 0 # This is now NOT standard LAL convention!
    inc = params['inclination']
    lam = params['eclipticlongitude']
    beta = params['eclipticlatitude']
    psi = params['polarization']
    t_ref = params['tc']

    # Using time-frequency track of dominant mode to get
    # the corresponding `f_min` for `t_obs_start`.
    phenomhm = PhenomHMAmpPhase(run_phenomd=False, mf_min=1e-20)
    phenomhm(m1, m2, a1, a2, dist, phi_ref, f_ref, 
             t_ref, modes=[(2,2)], length=10240)
    freqs = phenomhm.freqs.copy()
    tf = phenomhm.tf.copy()
    ft_track = interp1d(tf[0][0], freqs)
    f_min = ft_track(t_ref-t_obs_start*YRSID_SI) # in Hz

    wave_gen = get_waveform_genner(mf_min=f_min*MTSUN_SI*(m1+m2), run_phenomd=run_phenomd)

    if ref_frame == 'LISA':
        # Transform to SSB frame
        t_ref, lam, beta, psi = LISA_to_SSB(
            t_ref,
            lam,
            beta,
            psi
        )
    elif ref_frame == 'SSB':
        # Don't need to update variable names
        pass
    else:
        err_msg = f"Don't recognise reference frame {ref_frame}. "
        err_msg = f"Known frames are 'LISA' and 'SSB'."


    if sample_points is None:
        print(1/params['t_obs_start'])
        freqs = np.arange(0, nyquist_freq, 1/params['t_obs_start'])
    else:
        freqs = sample_points
    modes = [(2,2)] # More modes if not phenomd
    direct = False # See the BBHX documentation
    fill = True # See the BBHX documentation
    squeeze = True # See the BBHX documentation
    length = 1024 # An internal generation parameter, not an output parameter

    shift_t_limits = False # Times are relative to merger
    t_obs_start = params['t_obs_start']
    t_obs_end = 0.0 # Generates ringdown as well!

    wave = wave_gen(m1, m2, a1, a2,
                    dist, phi_ref, f_ref, inc, lam,
                    beta, psi, t_ref, freqs=freqs,
                    modes=modes, direct=direct, fill=fill, squeeze=squeeze,
                    length=length,t_obs_start=t_obs_start,
                    t_obs_end=t_obs_end,
                    shift_t_limits=shift_t_limits)[0]

    wanted = {}

    if 'LISA_A' in ifos:
        wanted['LISA_A'] = 0
    if 'LISA_E' in ifos:
        wanted['LISA_E'] = 1
    if 'LISA_T' in ifos:
        wanted['LISA_T'] = 2

    output = {}
    # Convert outputs to PyCBC arrays
    if sample_points is None:
        length_of_wave = params['t_obs_start']
        loc_of_signal_merger_within_wave = t_ref % length_of_wave

        for channel, tdi_num in wanted.items():
            output[channel] = FrequencySeries(wave[tdi_num], delta_f=1/params['t_obs_start'],
                                  epoch=params['tc'] - loc_of_signal_merger_within_wave)
    else:
        for channel, tdi_num in wanted.items():
            output[channel] = Array(wave[tdi_num])
    return output