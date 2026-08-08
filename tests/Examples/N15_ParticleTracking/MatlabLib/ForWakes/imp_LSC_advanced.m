% space-charge impedance for Gaussian transverse profile with rms rb0 at gamma0 (in SI Units)
% dimensions: f - Hertz
function Z = imp_LSC_advanced(f,z,emit,beta,gamma)
c=2.99792458e8;
Z0=376.7303;

n=length(f); nz=length(z);
f2w=2*pi; 
koef=Z0/(4*pi*c)*complex(0,1);

for i=1:n,
    w=f(i)*f2w;
    if abs(w)<1e-7, Z(i)=0;    else
        Z(i)=koef*w*quad(@IntGauss,z(1),z(nz));
    end;
end;

 function y=IntGauss(z0)
      gamma0=interp1(z,gamma,z0);
      beta0=interp1(z,beta,z0);
      emit0=interp1(z,emit,z0);
      rb0=sqrt(emit0.*beta0./gamma0);
      alpha=w*rb0./(c*gamma0);
      alpha2=alpha.*alpha;
      y=exp(alpha2+log(expint(alpha2))-2*log(gamma0));
  end
end