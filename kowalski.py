from astropy.coordinates import SkyCoord
from penquins import Kowalski


def logon():
    """ Log onto Kowalski """
    username = "username"
    password = "password"
    s = Kowalski(
        protocol='https', host='kowalski.caltech.edu', port=443,
            verbose=False, username=username, password=password)
    return s


def get_pos(s,name):
    """ Calculate the median position from alerts, and the scatter """
    det_alerts = get_dets(s, name)
    det_prv = get_prv_dets(s, name)
    ras = [det['candidate']['ra'] for det in det_alerts]
    decs = [det['candidate']['dec'] for det in det_alerts]

    # Calculate the median position
    ra = np.median(ras)
    dec = np.median(decs)

    if det_prv is not None:
        for det in det_prv:
            if len(det)>50:
                ras.append(det['ra'])
                decs.append(det['dec'])

    scat_sep = 0
    if len(ras)>1:
        # Calculate the separations between each pair
        seps = []
        for i,raval in enumerate(ras[:-1]):
            c1 = SkyCoord(raval, decs[i], unit='deg')
            c2 = SkyCoord(ras[i+1], decs[i+1], unit='deg')
            seps.append(c1.separation(c2).arcsec)
        # Calculate the median separation
        scat_sep = np.median(seps)

    return ra,dec,scat_sep


def get_galactic(ra,dec):
    """ Convert to galactic coordinates, ra and dec given in decimal deg """
    c = SkyCoord(ra,dec,unit='deg')
    latitude = c.galactic.b
    return latitude


def get_lc(s, name):
    """ Retrieve LC for object """
    # The alerts
    df_alerts = pd.DataFrame([val['candidate'] for val in get_dets(s, name)])
    df_alerts['isalert'] = [True]*len(df_alerts)
    lc = df_alerts

    # Get 30-day history from forced photometry 
    det_prv_forced = get_prv_dets_forced(s, name) 
    if det_prv_forced is not None: # if source is recent enough
        df_forced = pd.DataFrame(det_prv_forced)
        if 'limmag5sig' in df_forced.keys(): # otherwise no point
            df_forced['isalert'] = [False]*len(df_forced)
            
            # Merge the two dataframes
            lc = df_alerts.merge(
                    df_forced, on='jd', how='outer', 
                    suffixes=('_alerts','_forced30d')).sort_values('jd').reset_index()
            cols_to_drop = ['index', 'rcid', 'rfid', 'sciinpseeing', 'scibckgnd',
                'scisigpix', 'magzpsci', 'magzpsciunc', 'magzpscirms', 'clrcoeff',
                'clrcounc', 'exptime', 'adpctdif1', 'adpctdif2', 'procstatus',
                'distnr', 'ranr', 'decnr', 'magnr', 'sigmagnr', 'chinr',
                'sharpnr', 'alert_mag', 'alert_ra', 'alert_dec', 'ra', 'dec',
                'forcediffimflux', 'forcediffimfluxunc', 'limmag3sig']
            cols_to_drop_existing = [col for col in cols_to_drop if col in lc.columns]
            lc = lc.drop(cols_to_drop_existing, axis=1)
            lc['fid'] = lc['fid_alerts'].combine_first(lc['fid_forced30d'])
            lc['programid'] = lc['programid_alerts'].combine_first(lc['programid_forced30d'])
            lc['field'] = lc['field_alerts'].combine_first(lc['field_forced30d'])
            lc['isalert'] = lc['isalert_alerts'].combine_first(lc['isalert_forced30d'])
            lc = lc.drop(['fid_alerts', 'fid_forced30d', 'field_alerts', 'field_forced30d',
                          'programid_alerts', 'programid_forced30d', 'isalert_alerts',
                          'isalert_forced30d'], axis=1)

            # Select magnitudes. Options: magpsf/sigmapsf (alert), mag/magerr (30d)
            lc['mag_final'] = lc['magpsf']  # alert value
            lc['emag_final'] = lc['sigmapsf']  # alert value
            if 'mag' in lc.keys(): # sometimes not there...
                lc.loc[lc['snr']>3,'mag_final'] = lc.loc[lc['snr']>3,'mag'] # 30d hist
                lc['emag_final'] = lc['sigmapsf']  # alert value
                lc.loc[lc['snr']>3,'emag_final'] = lc.loc[lc['snr']>3,'magerr'] # 30d hist
                lc = lc.drop(['magpsf','sigmapsf','magerr','mag'],axis=1)

            # Select limits. Sometimes limmag5sig is NaN, but if that's a nondet too, then...
            lc['maglim'] = lc['limmag5sig']#.combine_first(lc['diffmaglim'])

            # Define whether detection or not
            lc['isdet'] = np.logical_or(lc['isalert']==True, lc['snr']>3)

            # Drop final things
            lc = lc.drop(['pid','diffmaglim','snr','limmag5sig','programid','field'],axis=1)

            # Drop rows where both mag_final and maglim is NaN
            drop = np.logical_and(np.isnan(lc['mag_final']) , np.isnan(lc['maglim']))
            lc = lc[~drop]
        else:
            # Still make some of the same changes
            lc['mag_final'] = lc['magpsf']
            lc['emag_final'] = lc['sigmapsf']
            lc = lc.drop(['magpsf', 'sigmapsf', 'programid'], axis=1, errors='ignore')
    else:
        # Still make some of the same changes
        lc['mag_final'] = lc['magpsf']
        lc['emag_final'] = lc['sigmapsf']
        lc = lc.drop(['magpsf', 'sigmapsf', 'programid'], axis=1, errors='ignore')

    df_prv = pd.DataFrame(get_prv_dets(s, name))
    if df_prv is not None:
        if len(df_prv)>0: # not always the case
            df_prv['isalert'] = [False]*len(df_prv)
            # Merge the two dataframes
            lc = lc.merge(
                    df_prv, on='jd', how='outer', 
                    suffixes=('_alerts','_30d')).sort_values('jd').reset_index()
            cols_to_drop = ['index','rcid','rfid','sciinpseeing','scibckgnd',
                          'scisigpix','magzpsci','magzpsciunc','magzpscirms','clrcoeff',
                          'clrcounc','exptime', 'adpctdif1', 'adpctdif2','procstatus', 
                          'distnr', 'ranr', 'decnr', 'magnr', 'sigmagnr', 'chinr',
                          'sharpnr','alert_mag','alert_ra', 'alert_dec', 'ra', 'dec',
                          'programpi', 'nid', 'rbversion', 'pdiffimfilename',
                          'forcediffimflux', 'forcediffimfluxunc', 'limmag3sig',
                          'pid', 'programid', 'candid', 'tblid', 'xpos', 'ypos', 'chipsf',
                          'magap', 'sigmagap', 'sky', 'magdiff', 'fwhm', 'classtar', 'mindtoedge',
                          'magfromlim', 'seeratio', 'aimage', 'bimage', 'aimagerat', 'bimagerat',
                          'elong', 'nneg', 'rb', 'sumrat', 'magapbig', 'sigmagapbig', 'scorr', 'nbad']
            cols_to_drop_existing = [col for col in cols_to_drop if col in lc.columns]
            lc = lc.drop(cols_to_drop_existing, axis=1)
            lc['fid'] = lc['fid_alerts'].combine_first(lc['fid_30d'])
            lc['isalert'] = lc['isalert_alerts'].combine_first(lc['isalert_30d'])
            lc = lc.drop(['fid_alerts', 'fid_30d', 'field_alerts', 'field_30d', 'field',
                          'programid', 'isalert_alerts', 'isalert_30d', 'pid'], axis=1,
                         errors='ignore')

            # Put magpsf into mag_final
            if 'magpsf' in lc:
                lc['mag_final'] = lc['mag_final'].combine_first(lc['magpsf'])
            if 'sigmapsf' in lc:
                lc['emag_final'] = lc['emag_final'].combine_first(lc['sigmapsf'])

            # Select limits. Options: diffmaglim, limmag5sig
            if 'maglim' in lc: # if it had a det_prv_forced
                lc['maglim'] = lc['maglim'].combine_first(lc['diffmaglim'])
            else:
                lc['maglim'] = lc['diffmaglim']
                lc = lc.drop(['diffmaglim'], axis=1)

    # Define whether detection or not
    lc['isdet'] = np.logical_or(lc['isalert']==True, ~np.isnan(lc['mag_final']))

    # If there were no prv dets at all, add a maglim column
    if 'maglim' not in lc.keys():
        lc['maglim'] = [None]*len(lc)

    return lc


def get_prv_dets(s, name):
    q = {"query_type": "find",
         "query": {
             "catalog": "ZTF_alerts_aux",
             "filter": {
                     '_id': {'$eq': name},
             },
             "projection": {
                     "_id": 0,
                     "prv_candidates": 1,
             }
         }
         }
    query_result = s.query(query=q)
    if len(query_result['default']['data'])>0:
        out = query_result['default']['data'][0]['prv_candidates']
        return out
    return None


def get_prv_dets_forced(s, name):
    q = {"query_type": "find",
         "query": {
             "catalog": "ZTF_alerts_aux",
             "filter": {
                     '_id': {'$eq': name},
             },
             "projection": {
                     "_id": 0,
                     "fp_hists": 1,
             }
         }
         }
    query_result = s.query(query=q)
    if len(query_result['default']['data'])>0:
        if 'fp_hists' in query_result['default']['data'][0]:
            return query_result['default']['data'][0]['fp_hists']
    return None


def make_triplet(alert, normalize = False):
    """
    Get the science, reference, and difference image for a given alert

    Takes in an alert packet
    """
    cutout_dict = dict()

    for cutout in ('science', 'template', 'difference'):
        tmpstr = 'cutout' + cutout.capitalize()
        cutout_data = loads(
                dumps([alert[tmpstr]['stampData']]))[0]

        # unzip
        with gzip.open(io.BytesIO(cutout_data), 'rb') as f:
            with fits.open(io.BytesIO(f.read()), ignore_missing_simple=True) as hdu:
                data = hdu[0].data
                # replace nans with zeros
                cutout_dict[cutout] = np.nan_to_num(data)
                # normalize
                if normalize:
                    cutout_dict[cutout] /= np.linalg.norm(cutout_dict[cutout])

        # pad to 63x63 if smaller
        shape = cutout_dict[cutout].shape
        if shape != (63, 63):
            cutout_dict[cutout] = np.pad(cutout_dict[cutout], [(0, 63 - shape[0]), (0, 63 - shape[1])],
                                         mode='constant', constant_values=1e-9)

    triplet = np.zeros((63, 63, 3))
    triplet[:, :, 0] = cutout_dict['science']
    triplet[:, :, 1] = cutout_dict['template']
    triplet[:, :, 2] = cutout_dict['difference']
    return triplet


def plot_ztf_cutout(ddir,name):
    """ Plot the ZTF cutouts: science, reference, difference """
    fname = "%s/%s_triplet.png" %(ddir,name)
    print(fname)
    if os.path.isfile(fname)==False:
        q0 = {
                "query_type": "find_one",
                "query": {
                            "catalog": "ZTF_alerts",
                            "filter": {"objectId": name}
                        }
            }
        out = s.query(q0)
        alert = out["default"]["data"]
        tr = make_triplet(alert)
        plot_triplet(tr)
        plt.tight_layout()
        plt.savefig(fname, bbox_inches = "tight")
        plt.close()
    return fname


def plot_ps1_cutout(ddir,name,ra,dec):
    """ Plot cutout from PS1 """
    if dec>0:
        decsign = "+"
    else:
        decsign = "-"

    fname = ddir + "/%s_ps1.png" %name
    if os.path.isfile(fname)==False:
        img = stamps.get_ps_stamp(ra, dec, size=240, color=["y","g","i"])
        plt.figure(figsize=(2.1,2.1), dpi=120)
        plt.imshow(np.asarray(img))
        plt.title("PS1 (y/g/i)", fontsize = 12)
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(fname, bbox_inches = "tight")
        plt.close()
    return fname


def plot_ls_cutout(ddir,name,ra,dec):
    """ Plot cutout from Legacy Survey """
    fname = ddir + "/%s_ls.png"%name
    if os.path.isfile(fname)==False:
        url = "http://legacysurvey.org/viewer/cutout.jpg?ra=%s&dec=%s&layer=ls-dr9&pixscale=0.27&bands=grz" %(ra,dec)
        plt.figure(figsize=(2.1,2.1), dpi=120)
        try:
            r = requests.get(url)
            plt.imshow(Image.open(io.BytesIO(r.content)))
            plt.title("LegSurv DR9", fontsize = 12)
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(fname, bbox_inches="tight")
            lslinkstr = "http://legacysurvey.org/viewer?" +\
                        "ra=%.6f&dec=%s%.6f"%(ra, decsign, abs(dec))+\
                        "&zoom=16&layer=dr9"
            outputf.write("<a href = %s>"%lslinkstr)
            outputf.write('<img src="%s_ls.png" height="200">'%(name))
            outputf.write("</a>")
            outputf.write('</br>')
        except:
            # not in footprint
            return None
        # you want to save it anyway so you don't do this over and over again
        plt.close()
    return fname