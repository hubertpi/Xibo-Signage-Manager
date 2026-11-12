#!/usr/bin/env python3
"""Create the Raspberry Pi Imager 2.x manifest for the Cafeteria Xibo SD image."""
import argparse
import json
from pathlib import Path

root = Path(__file__).resolve().parent
RAW_SHA = 'd23da39476ead9756445d435a6f3c8176f33e6c29ec30cc41a062dfc45de2e56'
PATCH_B85 = (
    '{Wp48S^xk9=GL@E0stWa761SMbT8$j;z6%A%v}HgVg9%O&@F1|wOcSKW+rdFA{(Ihr8`8-NZ>;(*69}te=C?Z0|+q*k8PVbjF6gq'
    'EBS?Rf3$qO$N`}Inhbp-xj3rH6<4L!EL%2<lrRjL4D)IUR52{~55`xenVcE<DYvoJ4{wx_JWGhx=tQ0YU$hBh?jb%UQd*nPxWr$%'
    'Q5WOIGzuI6HlZ;^B>ef-MM+%}g9?qoS0q|k<pV42WP?lJj+N2zEPAqv&y*R%yQ;1uXm4rU*>Tjvgv5w+9~`Kf^-kgCHiv%qx4KEu'
    'cZ$a*Rp+2`&)v)lGlH~0@+~iK#)5<yJuyK4?B30;_8aDOmh3>V$wPASpsOV_?++*rV>3rZhI1_Mk!ggUhjMA3GQZol_Qlc47<SjI'
    'rRi;jX~zP2zv{P9C*cwEyf*H!a+>q9&7QDoK);J!^30TZlPc#q57gGEyp$2PH+L6D>r$JCOJ6%>Lh<gT2K;H6J2q^t5Ospl_Yiyb'
    'dAQsaA%Gt0@rw=WbnA|Bls~@`Aa^P#+$@Q)5HC3S?pgT%-UkZUP#t<L#BLNp4rK@d|1+5<fZ<qq?HfDir~I`6P5}WB*ljz<3rb&9'
    'P|f@;5+HUJd~o+C>3;hjV9qqt0FSS&tpoV>(JT^MHp+%-MH(|v2wmjT0M>?oae^T`N;5j9TCz9p6vB7fjI?r6%JK$DJ*G#`ee8Z0'
    'U)$XoP1Wvlnf{<z+8M24HT@ogj5Q}6Cuq|u>{~W^%Aq#sbV${eoxqCF1xMhR%KL(x()l2VjP?J(z}ke-db2y9PF#ZY#<|yKhkT*9'
    '6-w31+mz-Vx|7H36pS2J!j|tuwwg?hIv)+Nyn6#sx?C}I=~1Hr-901{6qug=YT!U~Qg9ImVTUCf9|tF!5vJKK1&A-rnpE9P10iUp'
    '_orW(Oa3dY!7@dMAzGTq(a>`Y!dn_px$&Q-%0{L%1JT7uj1=SmvE1u_vfnaix>V!MX0B+IdM9Yaoc<R(EDXzu=_%%g3EYz=c^gAQ'
    'v$0kEkA^sa{CF$=aK!+)t8D!C3)`EuH3(^hdM+{y4$4y2y*$s4q=PeCV#5#D3Em+F@vi3^|MS)@NfBg5dYKx`J{-zecD{b*rqW)^'
    'ciJUcm|B>7O!UMke|p~(I?)it9QSs=_`;3Ud@YS=!7li-7v05|+Q{EUI8OXQNkMZlr!Q_O=vnAUf4RGB@B*!GVgHNSc7IZR+I9EF'
    '%!}*WNuRhNp0{%7clNsNnTm^IMo5#(Rt7UdQ^Q9NLTJ0oL}CSV^))S4(%Zu*l2WUN$EYoUS)B;y^?++JkZ1Sy#ZU~cexui=^bFPu'
    's*ss2Y2R77@oD85Yl^sHl}0sbr=J7x)7CThwF!j0kXmQ7(#78f%eC+QUdVF_9hFYc6KbseU-<!_n;bcxMGDMYz5K{nf-|2FO4EL^'
    'zM%Rrc%FuB_h8U?pDJune_jO1$2@K+v<IHPs6peN!oOlj=JROAsVuhkXI|V%4t93%zt%;37tX^kCUi28E9`QPpDJDKUjG;LFH2aa'
    '9o2aXql30L1J90*=R8@wdODi-H*|~$^H1I1gS+KelinT3TkV!HQ5-y&L@lQLQhyLI^vkY+SHZfe-l?EsM2|x)tgiAW%5$C;BJhs&'
    'UgbbH{Yem3+{z0giZ=d#r*rxvp-D<jd^*xyItD{ptFDa(q)_Eb?hvvdjuyn%oaj2Ia|~Ca>g?;eWF!P<cPx;1xBztNE)3x!u)Q;{'
    'H%_Y^R7k6f>*B^K6>1<>MH%()KVdf$8(c}z%0rF?e^J6V=3%M3k>dD0K8w23uZSv3R=z;5dmaCGxDFvku7_lm`1{6EXTV_t9CJpb'
    'py2AeGL^kLjr}I-6Tps!VgWZkrb2n_)Kr`bM%?qVrlKi^ALeq}{e6`Ojgz-#*eyVjEE(<*ZJwMk!mL;4ALJJetL?zf4eS7@h#FCj'
    '1B-l{C0?4`f7mFM!ZE)yvBLll5EQ=#VEb-Y45gF$$zjvjR`qfIr;?c@&<HKb2C&JYXV%5iGm3aZzW5eQFfU6&?>=}qA^dp<R3TNj'
    '--!p<BmMs&H+%<<fRpX#ZFE=TD+n^}8D0|n<1^_hpXNhomb|}c`?+YG1DCO@;o?zBn*FtAop9*cD>lWJ?FVNXE{03uGbS;ftiw?$'
    'Yip!R>Y6dN6#u9sY%oFyAwE=|?jvj(;_7PF)Sw7U3RyoCf6UQ#KX769F}RY*KcSDlcsbA^ki&E}b1RuyRCZ_b8zvWI9FpSE=tm0X'
    'sx`jnUeL=0xm(%TTjZuMHx1V*f@lzxC*C1knmT?r1VIut%5IQUz|5GOAvx2qGiZ3dq7$<#HRrB0?2`07V1v|(=y^<c8uw7<E$>G^'
    '$UalEkWl`iHZy(GbfcFGvEO3jN}({5pznrC#1&*ra{4>*bJ1I&R%qgZlIsUGHHK-FMS=~<xPc31iuvzAv;PsU754`resY@hBw)^W'
    '37ufEHCH8WwH<#r)1S3uTBjk4+D$hw8B2ysG_@cQ1I{aj1M+Ag7Li3;5lt_Iu!V{~-L6dMo~D-6tGiH0`&+C$fLrcfA1aEgKGTk-'
    '!UH_n7@L|l0;AO5e0x&;jt~e2IqOht7EWO89qK<muxT<B(7H1;Tie+4a&H<f<n8<<KhuSCfH>o#fe5f$^X)QPMVAXC(|l{fQaXV~'
    'Lye^KeZ)2ezEy>OYh<bC7i#1KT&Hi{>09+NBXC<;cH#byW&2R2?oUsO8{Qbe7G3n|7t8`@9aN3c+ngkbZO+;BBbfFuB0G@@9(XDu'
    'b0Vn#i_l%zE<tDk&$Dcc!i?3)Vrw!p8i+z1cs4iTh(2(A_<>_h2pir1>AOMkBn5_6Iz8Dg3AUZCeuhQVK*F^kaB>iYQ2_>)2`9~6'
    'nc0LWhX<~csaAsbpD3V@qvb_z{26IQFtRbx<}J|o@Q`3(X1+pq4k~T7Ae&2)C~Y$r#o147lS>jM?T30P2ZphWDF7Wv0_!_y=~+u@'
    'RH2?AU<1twp7I&@fkLq00)TAdLWi+)Ch;dTWHcQlblg)eRU*7SFM>tk&8J{tkWx+%DIP<XJZ61+1Uzs3`nq(Ppqf7+k?f}uD;uGL'
    'xq&P9wh#)W6{?0TFrSIx95A8EfDGj<HR@V9eU<LnoOw@^EGckq4*d4LA@=R%==Q!RXRvP%bLcLnKi5na^v)!-wo^~LSDBnpcsLhv'
    '<n<$N`?5NpjI|4rTSMtrANvzUkyr@M%|Y$&XzN@e)3f|tH5fz19nwW~tSZ23->K-V(V_$2@P4QSb-wFB8*d(LU^XoU&2d?D@xV{y'
    'Nc;@~NHU5AN4OH?4z-;-N$zBSg}jYlXZ<C;`T61XE8~?b1tY2FE_51j@(TaT%rOf##w?VCs1QE9>4D&oFDQ}D{4%ni**oXD2KmWV'
    'JJpvg&LF-R!PQUq8Xwfs4wofLG5_A#o@a;V4{KPV+{nN)NE*dl`=db>p4+tfHqoNk(yskM=pq$l-(>DTzsjVcGZf{l0O+18%eRf('
    'Ubyz@EQ}fOMjp&hWYzpomv&AGhVCVvvpG(3rvIw2j*v5b$HK%A0kOl~dAFUm#mvui{5krpo6l?UvSshU4v3`~4S{$6i%Xa9JPo}+'
    'a$xsfPNum$lf*J%7~C*AR&vY55GpnrZw>2e^C^aOEea_qZY!Wr)qD%E{Ux)s^IA@7MzI##{eYcdr{&HJE@t_(1WQpCj;zUFt(y9P'
    'cY>BL$0~?GbcVXdHy1~8YJo%$o>grhtY4nET63@ildcOxO3Umj7a31BW?JPsnJkFz^lMn;g04V>-8#~?m1e;IbA1rVKpt3%1k@2>'
    'PQ|*SM*wv^ya2qtJ_}h*0p|Atj%fAYwU{)<IBLfGLkCuPTm&b$eo0saVv<xiwTrcZf&J_N7X~j*{3i|-qV9HTimi`>lm1`*Gy~c6'
    'G*xeH60{;|%0HUsU-Kl^BJwNdc_2{Qh9ImEy8W4wvE(MLyda&OCq_K73%F0nCfrX+pc^+@Fm+S&bhYBHL=wL8If6`Fdsxcq1e`!~'
    '2CjI;H-o_U5nbzbUD(%x^|;@s?Y6gS!X=`f|0L>|qefGJeaTz3{n;dO2nsT$NYQFxX?C{Y3WllRwp^7O7t@M?6{~ZvpEwvcs*W;~'
    'K{Ok99b6QaZyuxqu3<f9YS1en@vm0tw?eam>trDd(N*FOJ0-S=w`a3}ry0=*-RfoD#x5MC#0eMH*>d|sBtoFUWI==GDn~l}q|({}'
    ';Fq1f8WleVu@iuz2&UFv)!Uyjg+i|MPer==>2hi}pPr92+;bw;-`SRzMANd^NjU9OTcHVoO961Jpw>guldxr^aqmkIe`4^5yQMMv'
    'p=T?UOZM=`^<NXsHT|I_+-rRZXUD*COq>dvSJ&R9aG1vPkpFO=bh#b60`h=GQ+A@S`bE_gVGmU%^q{8sN%tIv62SGB*S*chg{NL9'
    'OCheaq<FJU$$UkcF5)hbE7b3Lkuecjq+5gRu2)VBqvOJjt&~-yko@9M@D_%bEm`O70C<rNsyi~^O#JR&a%eJx;JU&yE_LHv?DA?M'
    'ELG?5Z9uztyWk9oP!F^C<J+`U*j5Yd^`1&LU2~l|Qf*Yvs{I9qxs(OqGp#!BU=y8oCpI<xV(r7?DP$Whpbc~k5wW-1mMJ%12JDNC'
    '#JX)-9$<siHeVc$bx5iN!}8iSSB?jEM;3HOV#*t;41%V~tD+xiq5uIQ(f-N&>Ki#S(bTh>NY)v=z2@$jv(DA%_yY;0Mz}nX1XJkN'
    'tAI^+Eo-0ShZtv&-`@EHgk|bq?rhoWN&PuR-~wa!@p!o%yc0xFR<s_7G7g7|3Cj)h%2Ymjj(g<@vg5486%~~wpCXdb?2XIBNPD-H'
    '4R6S!sULh#&`@_QJA@oF|Bnd4W4||1j<YP#ACZtGr#wOLW)@~$G#)wHV3gG;)8b#!Pb$Cnh)u3rXmLZQYmN{K(usoHdkTTG(b1%^'
    'OPtKIj_r0GtBLC^qQxZam9Y~~o9#QDG17Bc=xG_*QJ8`DC)6n~z=;&(`3TrY8aEiyJ1sLA6U|=6M;CG*UW1E}B{^Y2Cq^4(9P6*E'
    'nnEhoQ~wbK25?HiBoblCW4)!xQ)rKk^cG5Wn3vI7cO~)wi-LpCwvkw&fJbY-3u}n3Ew|1eF7yN(R9spQyZFJ2QSQENg_H9%C#Vf<'
    'qcf5R+p|2MxzYLHp^`w#k0gNMO7{;_|JNI^J12ciG?Eam-uk^JPs>GA2hzO?b&+luymcY~D7DTPh`^XTJq`sNB`=ZA$Y63Du&n0L'
    '|8(uw^U5}9#XfWHKK;3AD^gJO=PZz@FYnif5UX4LOwB)#1`&vT`q&O8GRKN1dZ6<O73{L@i{ViH70K$b%pSFVFI^#fvj>bC-d<*|'
    'T@QfeJjC$@P>DRJd=J&DJdg)AUMV$E<n@r!R3&9$*N<Ahh<91Y3Z%^F70*UjKYj2XwnV9Ev#1mvMnT35o!wxj`~0NRr@$lK6E2IS'
    ')>rm9rn`C}M?vLg&6%F7E%`b6E0vu54V4uxukF*=(iOE`E7V=E7B2;BY<P8lvE+-Bh+{>q?`d1(-WFr&?x<fGW`xlc7pra4{uJV-'
    'PA@jJkV|r*3?Le^`#%(ru0GFZCEB(-Yy-)K9)=b5mw9X>=i8<1`;WsQM4SE~Ns{2Sx-oh=Kv}`-sypJ(H+)_j66hkPhKnRlrYWmH'
    'yt7GCKzJH4yWh4~5$wnQg4PGt!<;|&6PK*~djg?+u4B<$LIQV&_}s$^c+UFHPK}?%OmR;<`}R81<v_T<8KU<8Voyf!wFGIkr8t4A'
    'Qo#3!?$%Usy&FI;{|?bsSvqp8jTK2wh7jW@SfCPxhCq*@`^4%%qwA>_r)ZVS8Co@V_?3bliUlmup00*7f<F)J{_(pZXXVu_uY#Qx'
    'ArsJW29HAQfH`L>t*QV$(GrBl(W8sOPx5i3!h92RHf6m6N0c#r%P8KOPIbMH0GpK2!cH!Nmoqka<SE$6b%1mz(huSG67SPc-l6gl'
    'F=B&kuw)dwkXjiY+usSplQ9&w*B$`P;5Fse6P;*{y~$(ropmpmyh#Op|K<zzR<Q2E>V8}wgnc|N%NfKI%%T>t%~;IF?1o-g3s9Z)'
    'wR}^DZ@V2{e+1@H3~6Ael}$7u)lbqTews>zuos+Sk}bP9552bf<TrOp+oH;z(aQ&${+t>@($!;4-qS0Y!T51;?Avk4=Dj(SHfJJK'
    '5=(*KKtD=?<gkmdJ6T|8hrzOtPR-9DPZrYY#F?=BA{%H2N)G2Y<ZUBw-%gh~-H!ygT5i4x-%;vYCyXkT$O)@Fo#Ut0_8~IybnNLZ'
    'u!eb8;!IPmg}IX?0QcR+JS|^bT>qK8s>y~)gyxwM_*PqEWP6)%04J7-5TC-%qTt4yogYEGlwd*!8QPRfw49c|3e3cU%K=I^I^TH^'
    'CI0$>6_JQ1wM|?=Z#@_96$*=dwpc2KVV`Kmc(v~JW8Yf!w^|}cQua!Hf@mU6P~(O$p9@GUjd@N~;kMumR-Bw+v_s2TiQBkG1vBUW'
    'LxPdJsC$&HCorKX6d;CN7VGL*4Zw}%{=jh3lsq_F4nw3OV|}iVr&m)LZY8FUkVRFqI@E7iHVSgctu%P~#|I<3duMY&b&qT9<6*=g'
    'Ul{u>|HdduaOu6XFc>Z4Ke5_>M0kZEn8Sb?-g;4dAVw3|Z7~9F&i7I2kzl&IZgRD6aKp;M<u}+hd$t-WMZ&SQayk9=iJ0c!d{M4D'
    'G^@{TNbOs#7nDMkpIN+v9J=*hKQo;K7w9NG+j=S8Z^S-1laBC-+jKFAD6NM)reWtc+;D*V*tC&Nc^`R%qN#{Gd{YXWE|0nF`0Rrh'
    '-#EgE3nkAB+BHsL+!qi1V#O))Zh$~<hO{w7_U_Gde#<=$U~xW2s+XZJq!*QnXg7d1AR2W@`>gBEqD=r5@7@e~KUWs%(;j*py?Wtv'
    't(j*MIl%q^xCaHJU0sRN%sS$PcbM_d&0hpV9{r*XjZ#DE=2XlXMss(JzHTVL5j%fC%)>S9XJo-Br!onSdkC(D-|BnWujLv9dhO$w'
    'HebO6aEY3RzIu+!eSx9#5j?G~-S+2ff6XA8p?oZ4Y3tE>U^ZpYP`L?iC`4okN>S4xGTS5I1FFckYR@H-kV5aPn$yOee&%_TQNPsE'
    ')W~GtWEk~F)LTB>@Ny96?^fyl`4U|_Fmq5Dya~T13{&wu-Zo?3SWQYGC>hSdk0cas_oQyz$~!aM88U?GP~-Ij^5<|pal$UR>WW-{'
    't+ac5uuQ+&B+_;>RMxym^v-Jl9No-7U-01}3;o;ij5+1;8d3L=p;pA#201k|UK}bt?hNUs*;u4bdXH@rmVxVzzU8L}BV*YJx75p9'
    '!2CLW_C1-hCe_ptg_t(H%>zN+Hmxvx>?(Oeo6>y1g&{qVJV_pnco>GK(f27sJ4oN#j5T0KvDvUw7K&2E9Sr7@mrlX=J9^DR-Luq&'
    '@Z2N-8iw<YV7Y8o%nW?c{96_QDq^SOOJ@NQJapFq4dB{}riud(_Btnr{*-`5B7v1Pcub@xm&1~LymG1MwzhUU0%)4R?UJKB&h)aF'
    'o0_d^x6qc3aB}{cr86AKCDrLL-!a%n37et^D97T>9$s2a-7_*lp}0k55G0JzE@>8uZiE--M0;Gdu8{zJ-T|<2x-1vEln=-XQ0C&v'
    ';pk(q$0^nA7<y@6e;0ny?}Z;;Q+n3PnkXwCYem@|m2~Y8k<!#1k}|B&ZyA(&*XJ20NdcQmg`mvw#xtJmnewcmfZk&?cv>DsCUY5<'
    '5iLVBsp>=`npl`uP>1Io`e~<zFq1qSpdpJy0*bxfn&*E{{}Cp*-eHP}=Z~Arp407No)7c7(-tBXgrL5J>LVONvyj3!TLS?7aO4;!'
    'fnF^y5)1W`3{c(YuDfPz)v^)U@914AH@vt>>OHRE`x?bHYY^F}Qtvt+Gk29EH(WvOaQ81QTEN4T$9wU~m-LsJwAoOq0jY4SSSCy6'
    'HxWRzl-RP!ZasrX)5!;Q*!YtSy6v2YXqCs!dLYCwW!jeneii@UN{+BuyY;g~?Y{n)Q|b@4oBJGgrFkHbx{T#8dMJx~i>upW{sB|P'
    'YcxXDx^39!!`TS&d)E8*{|>($%|xoOK8(VHLUZlgNkxInVoWI+6}Yk*<8B6b>E0m#f-!j*)&$uFA6%Bh*Eyqh>&vszzLUS1H{KqQ'
    'dRt<b7@M8Wq66P=t>`jw;C0a(t`Mv9HK*Z^iUDC#t(aJ@=Qq-9IPs@Pop<h<)#bk!VW~a*!N{g^u-!__ke;<cu&*<;{Re|4j0rnq'
    'l%ad?*h3_?KwK^3^T9Nty|&+oBNp)v$cg@4-WF^JHny+oT1h)WTVg+qL#jmS(%|d+5qKuI31T?=#@1K~+?@W>+}6<xG+N4h0zIQ)'
    'q=yx992kRkF4LAZJB`NF9v<DA8ttmLE&_mj54na}r!1V=&DeAT%fxk`z9{RG6s|BlTmtSAbR87A;x54MF``lS_cI8GzaCysn;K!S'
    'UM<Hdp~F0YO##9M{Ec-s?RD+qzhjaqzQj_fN)$?55DIO~mS1nX)}PVY796dKw7C@B2!Vqk*+6}^s(}T7j6x3U<^z;f7sSAf#%wD|'
    'NVUfg(Va|kOW|M>e|>llT`hM;vmO5<X2nMET?$rpWd=;yuN6|6gvvFOZ*!@b?uF~{jjEYAP}0=rDv-J^Lw>6uj&uOFwECRM&tzfY'
    '`CcW_j0UhFjc)~U=oCSZ%YgRq#nD75;3d2Bg9pX46Xd%D<-6P!pdiPzpMHv(vBXbhHl~uY_-c5-Q_XaJ#H65RoVl>ys~~`_pv;}S'
    'WV)Sx)Fg_99S*O2ONl51M+N9OG5_E6@ttPBxo78(tdu?k=)lNT2F*-x)RTdLsimP|U?Z}3vz+{-eF!gxkzv7{B1cK5U-iqW`dLaJ'
    '<!L}A|6CX!^-)j(zQem&jS;$|=X6>ja#f3PpJqRMeCnwz0dS@sOjTr&+JhEHHC?lZ5(a5NKuZ|z6ljhvSM~|6?cV~;q=Evn$X+WF'
    'j(A-Nj}gzrq8+DK4u_CM&bIS(kd5LzYc7f7T%GNs^Mvbl*#rc~JHX#?WIblH$ekJ~Uq8_4q7<GKr$p79*Bc`jx=LC9)GrYjw6im`'
    ')5&I^jz+P%=L%cJ0kZ5V{6f@1RMxV#PC0Ss4YyYF^Czne#;ykZQo`!J3ViajRRfbr`fuGOvDxU7RO?AGZNyVZcM~HMTY>$e$S1P`'
    'YZFA`gg@m<+0LIL2zsb|XsOO+1FHNI{xhg^s?W$n&|hhv!&VjVsH;AY8tA?@x&Op<>mWH<KP~O%`VL-$QHRT>5v4lMS)2Y-V}r`0'
    'X01}y*X%W585WGOZD>&c?Z2$p)%;Uv3d;eiGSP&cp*gV7JS<BB_5==Hu;9u}xJ$7lNdt#CnL8F7MOzxIl0bo*tpv{hpcieOQW3sD'
    'zh;+dV-W{jV5zIY{FBmFK!Da|+m5K-^=#KpH+|LPRkZ|wQGiNc`nUK%vb$K~9e<_sm+8M<*NfNLpzeBCfcjpYQay}!z|f{eIm~Sp'
    '(;s!3pF<pEma*aC^N8w4Itw`x%!{DOcL=!qJ32f-R?Rdv{9Mk()ydwP0J$*I)?I0@fWn$jNUa7X7J98}M>a2L2%ME%#S^)t&^j$7'
    '%^p;s<^qIL4vEb4W_ZXQREHbiT9j=8KXW0C72oQM^@6YhwbBnX3MV+($K`lQgFozI=IGTM`H-jlk0mD=^<AT~n^onG*Ze^@;SNvi'
    'ReMZG=_X}l+3+A`k_A<++y+K^uomYC`blC8*xOH$1yMBdi=`~<4|=U|carcWYa;qlNgX1S=oJWPg-<FH)U0`R!iE6|qI*@G36P@L'
    'lCK^1HQFNNA=<?9mFVp#PxUb`Gzn52cH1@MYmGvw?R3e3AA#QIV-%cPYL<UxX=WB37l9dA^}+q};h;=vYYfqn^^5#Yk*H7*gPn}C'
    '_mq{OG{TtDT88LOV=bpb5F%_je7YOQ<W`1It<}7vi=b(_>qt0Ui7i?45jm7@VVmqTe1=YYS>A+R_^4u@6zjqm&V$cvu#-^G4AIA4'
    'KS~ST>^fYQ=DF*3`}rH%BBlL=7C9y>_8YmCT+?L!Do%!tMe?Nw|7)~Cg>hA!;p|gB%T@x__nN=K<dF4R9YX}CyrQ=>_fBd<L0qsB'
    'IfE<rd}4PuRx~#4iCKBeBa6#UuNciq_WKd`qoB3Ydm@o@x1nLpLk~bXx`J8=ZFF;O<ka=!3Gvj}W{$4{NLUbhQ2n9IR>{orjk4*|'
    'pH0q)@pZE1DvmtnGzpSzXRYxQI4b-ot}+GS_ju09B+V7Ua*rbkp;CNI)ZH&NsTx4uliI$2f4!3}kJh>|F7GZ2w4yc1De|%7G09Bl'
    'wpBuKk5~8o7H3e`KCg_R<n0iQai9!ib5V;F5U!QUHIXF6-oCOxEXu~4(9m-by;wI_;Pm}k+VKm~`kvd<+Yn8qyB=7hwZc*m#YyiB'
    '1J}mc?qo9ti1vfbMF<icA14UR8SgtE4s%0&HP~QB9KxghWndg_@fM3oCDW~N#2fCvbGnIhIJEgSor>T1slYgSCEPkYipw9N(63bp'
    '8n{H+AZ=vIGY4KY8k396ecj`W1JqbK9v<(MoRne2ueZM%YVFf~^07biERu_8gXsV1J+F(EnEF5!$v)G#HXT1)`sgVTVGQ2;)baAT'
    '|M<9HMMm_qkgR#|E3!$EPggVj@{Pj(Uj2Q~&cBZ;DlwlQmq=-vr|Qoj>+J=^a5`iCbl`aWQpy`nUO{cRW@anrcbx0ARNt=$-lrE='
    'Th1~S^-mQric5$_dY=wICr9rv#W1JAQSv{T=<V!5J*v}NfPcLrIM_&E`Y{gqvU}EF&*5Dn!4((n)mZ2G1|$<M#L-sJ91;bO=Cca~'
    '=eio9$b*9Lixm31l}Kh$9i-vGS#%@w`&GixESv)}PSf$Insr`?(IqG1%`$s;X%B=}JyIOFs%ehKTN7}Y3Xcpgq|k9o0tUy-P-i#P'
    'fGDm%Qm&}#lDvd8jMu1|3s_`Z97^O4tHimt6+ckR^*wZe$NA=+EX6Ut9_LXal0|t$MDsr37@jtcR5d@SB2G!0nYJ@7Obqrgzu2t$'
    'h>d5IsfB98W>x+HTCKC#4)Me1SDYQhesPJLOjt@2J!`|6&~9fl>dS=T;R$vQnbl9stzUz>iagb14a2xDjy?FWA8jb8$eyL25!oU|'
    'KbCkn&XC5QE4|?_Y@=%R#JAM!#ZedskaS6a3v{7g8CRy9CUYr@ONz80U0U9-C_p#)Cc2X+LhND`@Q!PZ1Ip+TDf;=0h|{G}X9wQ5'
    'VV}}rmSYN!AudU<&%i9fS>$Z;^~ysG{1duSYQNl?2Rda^6U0@do7H(9@8nqnBs)wOaGaa7q!pxtY<m(VadJ1w6yip@f?Tg*naM%x'
    'Bn=s=jr6TvZVvg^X%szpuXL=7Oxj{(+}rOtCOUA9Uqv$(=l{$ZDAJtFxs*1Y_xIrru~~CzQNJqOSS*oLxh%RC8l?+WOQMhzNL$dC'
    'kVqWpk3zE)Y9&dGGTT7e!F}3TS`JgPJM7Q8Rwi`&h5msMQ39=F)kd8cIKL5>hg+bE?R=kL-bx_$n#_^e$Q*c_Gi;4(Ixcie#I{4?'
    'Pc)F4ajn^hQgiX)gUNzAb|XVQ@an~!(ldiujLF?e63y&IA(-r`h0b9~^EM>i@YR;rNu6r}u`dTv+k8iQ+FYgrNFZfLAXz&#wySGi'
    '1894KSBUD;oh(B#47`jj-u5+|PUniDxx2bU@QHS7DA78qX&yNXD&_P9EeOurx94peedLN{a11LVX&{3!wIHY*KLBr4S8~t6F~Mdp'
    'I~70fRLEFAe1<(Wt%5PCb5kH5ItLuGc(5bLy7dyEnR4`4Ik+O~@I(HfQxrFM##?b~`DUqfNMp9pj`sU$skZ9_hm%bV)b^z4K6lpK'
    'x6Ha~zFJPo%Gmbu0Oj4zY2{ES5QijSXk2e09Z4*K?*^b``73Zx(Z(6M@~mgOjO=ap*2Z;O)M8;i>J-_*kBe6t7t&`%;2r$H3CtF`'
    'Rsvo|;UB!xFDpZK4Xv&2xzF#s%R78e@J4H%Cg0<X8(p=T!u>DzF>Yw)Fg@;8Od$@GIEhxQWgcWrBG4?FVroX?=P)&ccJjBz1bxh|'
    '1lV8XdR<6JHda&LzKFiMwHhqj2l=PDKd03>5O!=GugHDx7<UQCMr<R9gQ~cCEH`4^!XPQ8qEv(u0(EY8Lk8Jjx^77nVPOwTnclVv'
    'g!Il#auw^sYHrO}k#ZhLkO)a|M>GLC^Zb*OT$djb9oXO{L3}3%9~<(A2*zb4_n~1eLniCyCp<uU2KLhs>WwTH&iFr@$A1i^WquQj'
    'nFdk$gbG)Wu2{$rcKEe0vd?sg5g+mfjsU9?_erysqo+UAez4Hi@DjN!+ABibWv)01m#xQ(??}iC7BP5$BFtoDvrFTA+J^@7h{hsB'
    'PzBqGa9gVyi2AUd;;}Z?UB_bleLzNqbrpNbsXmOCBH-?*eS-UNTgAzaqtiBK5!3r`3(<F>LD$lji~lv-!|VMlhd8JufU%%fjhswU'
    '5@g^yLIZW_pdZSZz3ivwU97S3VFYp;U<jL?-1+n#d_@+2;~a!a#MyttR;FKT(Yo>)fle}-Txo?NH(@fZVBPmrPkW~vii8bK>ooHF'
    'S)6EV4t@0VFWKMxVt^4)Sua3(uzkyT?fAl*H*1vjA)o^C7{n;}NLFgZzth=*{|J09K;IAdYC^J0&O@-lC{ZNuRbrWBk0^#a#Nry`'
    'B94d|*4>j=#&jS+bT-?anwpZg5Y=H8?g9*I7_X(3%x|Zx%)ZV4nR<4zpPF8jViFhScz1so@D_N{O=Buco^na+N6FUR!38wgu>Sp<'
    'fIO_*PBuCmYFgk*eghKC3bRAEFb?PQ=rTJ6sDQ8;o+EGOjAU;;1P>K{A|ts%t38gYmOCqB9u<O>-BkjrM|Ew{J5WDK)6Az8=OU7W'
    'Q;?G4^CQs6`@#oTPa2IIaYi~*#e7`A+rwSih&NSRks=a88;Zee&6H0NA+Vfj-l@68Q0Eg`;JQF91{jlVp(tXeIxf)<5a36n4lWNw'
    '5U?95!5v~T$Mk=Pk7YzrMrtoK4He%`C}i<NB!v++hwyV@!Cb&K*xS~C{b|obAriaa)o;y&@ix1^Nwk1BA$c19++aS4QX6heW8982'
    'SQ@q_k*+?}>WF?4_vqEPB=l5#s{~B-yq*C+_>@u=iKM^pg+g5RGCMdn?OT72{B?uAIx9_$T2c@>4!>`@ynX_Eb<cv5i`XDn6#Pmu'
    'ANwaXLEi5zCU%3luS8SURZ1_kYSddjeRVaSyS+=CqBSdoHQc~g!5i)CFPIXzdese3HzHA7GI;!;90vS}tY9Kr%H&N1Ug%td^)~Rj'
    '<F}Rpk>^S6x}H`?=`eEYEb2lsvKvl6*dR(BFh!{C3?O=1e`L=%IY>WyO1sa$BW3@%3A?AC3eeqwgR$v#V&)Iktf1RzTr?W;JOX>e'
    '6W|lPp4o-98dT=QAU%ViLRwkq&|`@Hlg)$w+c>&x9~<X5*M|+b-Mu&1{8}>Pzq)`MvZb};Dmtl)_~L-t2bxn5AB|Qcs$>&eSJ^I)'
    's1br05MjH@AUIMVT6XmZTq0}bTh_fCm-YhnWwrRV=l^o7E1@#J8=zQpf7->XVSCtya|XNQrH6N1<8g|g!|9BwqM2OG<py=3E@E%O'
    'QLsmwzm@FzNp^$^W>duNot%BN0cOP=Gsr&jgzD3hjKxwoP6S;CvPvGfyue|vasGCYcW2FS^w<A(t=FH33D3g1%)KNDLdL1y)l+VJ'
    '#~@tU2g)<SikOKHLEZ%4yIv@_iAW{TX8dlcg-j7l)C@zuvu=@O7rO&ftHS4Nhqu8H<6G1#H6uQdBk<niTnTiL@RMV?LCJ_TRL}}W'
    'BWOto@<6(q;AcWvW?|osiN@l}=rcL%Kg`iTUf}U6ncR7>__h1C7!{>x;d?HghhMVbSP~UbuZmZm+M>b#2}at7`SwFKtZnP|T;XAG'
    '7QKkJ!9~Ap>19QIsogTy2E=U569mH5-=td#$%&Cy?Y|GxVA@*oVco!_8UV*9b+ip`PHT@SCc!pafSd0%b{PF7cky0?Nt78E-9a^x'
    'A>(arF+jGZ7NAP^uZuml$0~kpp2stB*Qn_nVt`wYTyrCTkjoU+J}Jvm(QH!r2Z2tKHHf(ox*PIR?S;)rcc6~HGZ9DOy=3fV4rtFn'
    'U9qaYN2ucdzW`sWL;4H+*=5C<J}6(!tZ%T6NU}~RPLKu|vPgSZ2gs9TfxN?S+q`AQJ&*^(M440|iaG3ArP~6X;XOotfqba=S>><!'
    'D&p@6OY(wf4#$E8J)TVK)h3?$?F~61&l%YjD7{kGknTQ8b?9vFDs!?gQwyP-39_QbC<)@W%W@gHFZ#WSYUmA*)$o1;J9~Mk(QJSH'
    'nNlj~EmcZCNo@$Qurs9srq(M!gaK5)r;Uf{bXRPsRCf3NV(8(VcgP$n7o`PK%_1a(MCCZ8ZyNWr@IlJWtZYXsqAT;PB`X>4{Y(y1'
    'T`+u|1xg`3;I@SvesEDL-^l917;b_M4C-TdI=1_vOzlks%{YbhwA;?x`GqT!Ck;sqL3*4%I)^S^M%l|t{CDqURPtC_1(DRKGuaz>'
    '+d*JSbw%7a0~f;XV~~zL%yCJsaS@db%bjZA9SR_>r+@ps7fr-P6}9I%Gq&s@5f;xf)Q4pd6)ng*u9-;D)fJ6Yz)qbYU<WYLeQ6kA'
    '75Ni!hLfyNOM-1=eJZv0n`_`8P5MWVHl2To;av;N&?WbW1w$3kucq|QvsV-Tt`H!g_GDNJ{HS4gfoQNb@4;rD0M^(|ZV==8-B3)c'
    'M9uMXCy#^DWMKJng|6YnmUDs(Ki$7l+3)Gd=-QPxs_9+D6Y?>%p{%gWBsZn4ei(sR#ZFiI^Rm%PN<7bhp2}1CV1_R4zgP;Hg>F0m'
    '8e8UJ^qBw;#33KE>894#hGA$EjSw(=RusX<y%;v!^IKlk!|#Xigi9O}RhMo*?jL^v<Of2%t#C(=S^O6j?R%*ZZAtZ$HQ8|4D^)){'
    'XR24|*`9{DUeFh-HtZ5g5--JqOeSc-+Z3VjzKBN2WLR;%b{1jZz-ny9?<${Z4<)fAiH*9#J{Zq`;F##m^VRl{b@kY`^BS`SKQ5<t'
    'bLUW5&}Jz@uS(%s4dUP1+tRZ=Y5O<E^N~ztGC<c##yHH9f^l!kLu5S%_y;T#y7AcS8GuI1MhE!gUwnrxa#Y<)HgVd|FeX_F_$fAe'
    '+Dsmi2t@|U>sQDb_0bw@o+GI0J~egXi<-Si0XM3I6(#d)z^2<zj4IQBO_n1LZtU)sR=LOJwliS%2(JU?g5yB5{?tk|8WxO4t>Rp<'
    '+{On!hf1~jsjM8A{WQ-bE~?$$VyZ6PKU8>!EBk@dD#YWWcJsne;QwOLhvc24eTM>R)-HZ!xve4y3sW9BF?p!?-!*;@FGLCRn(Io~'
    '5-L#>jq+%{LZ_3l!aWJzq0KOk_T6gU5jiohwLGrwzh>6(dyHiMG&;51TU95qZ|^nDVCc6$aJ{+K2MfPZ?kLFZu9Pw0e90PTmHTn8'
    '<;ia@PD+ZZ^T$rfs_H92j$pblYrHdJ$ahyH8bKzxI4e=d9C-M9bg90cSBt};Shj&!G)@G^&pe#vsqrEQ@n0C^`&trU1}Z#$xbQi-'
    '{s02o(%^_>f8yhzIOXCtOMe?ya%CFy{@PVaSsBrz)+l`s&a?}G>?rY(O?m|HlW{Gw(Cd&Pem7=P$!7rh_ZA@q5Xz#r4%vedsMYaw'
    'NdBvhWqv2t0Ql{AbOHfAju%qI!b%Oe8x;J9r2LS<<Mc;U8ubCWLTk50#Qz;zsgpBTmCnhf;9QbzAIJa>ec5&|>rM_z&3mJ}|GHOT'
    'BuK>8p4@1x5Fp9x@K1LSTJsWBts%6{TZCP)ge%3fB-9bXxT^$oQ2)%lzO@UC9f*kT<XiiTMQVjzba%ZLW-oQuM5w-Sq$C)Gk`oSi'
    'ahv=T^B>%B5G82i{Fn6sNmv#(mji2ks|R`Fw^78(lra2RrA=xN1<~_mJxv)*PFP4T9wzVD`#^z5&g?fvIz&+3$M2h|G$OB))02IK'
    '1(r<In<mzdPfW(;JJa&JY1snaS0u*CZBc03G%uTU4=IMM<r`w#IU|j5fYPV<{r!!tKnP#SqI%0v7c7#mWQxJ1uYE+$S&E*gf3Li}'
    '?y!5_AYQVY|G)hI(t47Yl369zgr;{cBXS_+_vkxEh+yCR6A_)zdPvU4A>ajiM%TV(lJ46M=-6+4199o^XsFXW?g(&!vynrN+0FoM'
    'd+Y1jiCrCmaRafXj+OJ6|E9VpX3Nd*vty11bvu>M0E1ft-}a$Qk^%v3Vu*Ds<FFD@F3sR@L*Eh*5mQy!qg~&ybCFRx$Lhl%qGsKo'
    '=DjIBC?9Uo42$Kfx4q>Up9%iu&-)KpuIgH`@2iuR_Gc=ejUaI11jfHMTaxE}1AIM*h=>zAdalYUhPb;rbW|2A*F>$&vi0e(iHz9p'
    'o<M+n>${N+Z*b~!ZeRpK>6185oj14MAsKoPZTv*FQj#?-jQTh(JW%>?lR;4Z-L>TvO_IsB$<_WV2GB^eZ&}`qGc}Sl>b~{zEd=8$'
    'IT|!9tvBjcye0%oO2x8OI>uDU;`&eR&xiR)Laa#@Mt$*cXASc+GC<%gbKY7DF`>VmQKTp`qQ!7=$D&rQq9Bcps%><bot%1C1QwOA'
    'U#@>II6PiO@k@4#f2(LjhGDLXPhX9`foWyymDj}|&ufvBcC-Iy1Fd|XD8xeNY2hL2D7>PWSIyn9$nw)V%ZN>eN(kpuIVE{EIQ2Qa'
    'xn@ut0+vmF4;<Lo)XV0gdAsr)?b7V-T-UNK>+1hS!oF~QGB>t;H{$651JT7;eU2wr6qo-G5rUW8^49AGHE0Cs47%<4<^;SMuO#xg'
    '2NYFZ_H>5JY28F+@^>YbhQ~v~$l4Gu#IjXkL7am8gbSkhI7OP^64T>nLI;zsc4DO#%r~N4-GB)6jny8IQBVa_y_P&^qmd6Btk|aE'
    '+2rIAb&dINa!uw`qXTdj1di%Rza%5Kz-MWO+c0fAfkHliyVXBq87J~5h_r9pS2Vz~LxbS<d%g=-it|K9F*Hf+rUON-0jSk$`;R5`'
    '1N1&?LOF+Z+$yPYooGE8C@}zz<8n8$=qC5^wavhExxWnjHe{u|*e@*LinZX@(oHMeg^z{5B?P|D<G$G`r2QC)ub7KMkn0KWW#lZu'
    'Yn|Q#$Ha$x^r?C3pPskIa6!!BA}t$Vrfp_6Gp%a!U!qI_H~S09JeU8Vz2Km+=1le{qnJXx&r}wj$q%-1-!=+@#t5(t-jrzxMEiDB'
    'qzj%2IQHWPWN`;IH&?btustv-;rRU8H3jh~g+Gq-rsl|zM}7P}@;bm?Nf!-kIY^90Uwo{$Tmq<KKx7uF6<j6(I_LF(J@I3eXc%f6'
    'UCLSNHmogw1#n&@6-&om;=zn>ic1ha{j4b+mjvM~Q&=~9dzf~2G9D)_14JJX9$c!-Zbq85KT$p_iST|te9}o$>*PbY*SDLo%Z~HD'
    'YXcADWqCcy4o!4F|NDoE_Ts7!lrgOD#D<qVr56=BXxn{CWq%)<psfoXZ8~D~d~2-9z$F#}EH7{+rYo!%sd4tMM34LgNAEOc-2|K-'
    '{JgEL>@0@yD8QlwQs!n==-3K7)so_rh1p=@Xjj1%7tMxW_G9aMNvcV9+@Gu}G3$@MJ`CBAa30HgpXkb=X^Ud<Z3>vzu|;h4#*H^p'
    '4;n3s=YuSkj-ccf^LNg0W8%m%XJ<I4sIyRj`!K6<#YU(*E$QelB0+S`i*fJ<4tNWdnCB+kiM8r6?_*)FSqM5QWXz!2K?;yl=6xM('
    'AziZ_l$9y;NM1Iz)4-qeFgZ$ZGEHtM-HjgzETWSE!ofeH540W2hu>OZl2!;jyNx4D4-du>u1^ju7c0RI#gaK!-OrZPo&$18rR(<d'
    'If3xJwQ|M-IS!WEK45b)G)T8%kBQyNq)SHY`)MVER<wj_4#p`!4b-3E7+I3mcqbOK<U*#bLy}Y_L|da6#kvLhE891FrmM>z1kL#@'
    '9x4v5I))WI5sD!n%n@djXKAePl18-xH6rQ!TI2(uM%-Xg%<YmQ)h{NZp?u<ez>{IwkRV_HinYW#RWU9hFTFpj0vh@;71&hxM;k92'
    '9JU)AkO<#)&6KCJ2hzO+<Ts!q8JVL`QlM5EL)8YYJP*;QY(;}wUx|q7v6p151|{C6H3SDqXcGVcn5>s5@nP~!00HQ2u!9Kz#I7TE'
    'vBYQl0ssI200dcD'
)

def build_image(output, local_base):
    import base64
    import hashlib
    import io
    import lzma
    import shutil
    import struct
    import tempfile
    import urllib.request

    url = ("https://downloads.raspberrypi.com/raspios_arm64/images/"
           "raspios_arm64-2026-10-06/2026-10-06-raspios-trixie-arm64.img.xz")
    def digest(path):
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    with tempfile.TemporaryDirectory(prefix="xibo-build-", dir=root) as temp:
        temp = Path(temp)
        base = local_base or temp / "base.img.xz"
        if not local_base:
            print("Downloading Raspberry Pi OS (about 1.36 GB)...", flush=True)
            with urllib.request.urlopen(url, timeout=60) as src, base.open("wb") as dst:
                shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
        if digest(base) != "976766570bee2aaf3047dd78649cfe82abb8fe9687b7f15030cd533ba4e9f7a9":
            raise SystemExit("Base image checksum did not match; nothing was written to an SD card.")
        print("Assembling the Xibo image...", flush=True)
        staged = temp / "cafeteria-xibo.img"
        with lzma.open(base, "rb") as src, staged.open("w+b") as dst:
            shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
            assert dst.tell() == 6744440832
            patch = io.BytesIO(lzma.decompress(base64.b85decode(PATCH_B85)))
            while header := patch.read(12):
                offset, size = struct.unpack("<QI", header)
                assert 0 < size <= 4096 and offset + size <= 6744440832
                chunk = patch.read(size)
                assert len(chunk) == size
                dst.seek(offset)
                dst.write(chunk)
        if digest(staged) != RAW_SHA:
            raise SystemExit("Result checksum did not match; image discarded.")
        staged.replace(output)
    return output

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("image", nargs="?", type=Path, help="path to the downloaded custom image")
parser.add_argument("--build", action="store_true", help="build the image locally from the official download")
parser.add_argument("--base", type=Path, help="use an already downloaded official base with --build")
args = parser.parse_args()
if args.build:
    image = (args.image or root / "cafeteria-xibo.img").expanduser().resolve()
    if image.exists():
        raise SystemExit(f"Refusing to overwrite {image}")
    build_image(image, args.base)
else:
    image = (args.image or root / "cafeteria-xibo.img.xz").expanduser().resolve()
if not image.is_file():
    raise SystemExit("Image not found. Place it next to this script or run with --build.")
manifest = {
    "imager": {"devices": [{'name': 'Raspberry Pi 4', 'tags': ['pi4-64bit', 'pi4-32bit'], 'default': True, 'icon': 'https://downloads.raspberrypi.com/imager/icons/RPi_4.png', 'description': 'Raspberry Pi 4 Model B, 400, and Compute Module 4 / 4S', 'matching_type': 'inclusive', 'capabilities': []}]},
    "os_list": [{
        "name": "Cafeteria Xibo (Pi 4)",
        "description": "Raspberry Pi OS 64-bit Trixie Desktop; installs Xibo on the first connected boot",
        "url": image.as_uri(),
        "image_download_size": image.stat().st_size,
        "extract_size": 6744440832,
        "extract_sha256": RAW_SHA,
        "init_format": "cloudinit-rpi",
        "devices": ["pi4-64bit"],
    }],
}
out = root / "cafeteria-xibo.rpi-imager-manifest"
out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(out)
