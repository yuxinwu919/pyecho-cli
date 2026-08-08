% space-charge impedance for Gaussian transverse profile with rms rb0 at gamma0 (in SI Units)
% dimensions: f - Hertz
function Z = imp_LSC(f,rb0,gamma0,gamma1,L)
c=2.99792458e8;
Z0=376.7303;

n=length(f);
dgamma=(gamma1-gamma0)/L;
f2w=2*pi; 
koef=Z0/(4*pi*c)*complex(0,1);

for i=1:n,
    w=f(i)*f2w;
    if abs(w)<1e-7, Z(i)=0;    else
      if dgamma==0,
        alpha=w*rb0/(c*gamma0);      alpha2=alpha*alpha;
        Z(i)=L*koef*w*exp(alpha2+log(expint(alpha2))-2*log(gamma0));
      else
        Z(i)=koef*w*quad(@IntGauss,0,L);
      end;
    end;
end;

 function y=IntGauss(z)
      n=length(z);
      gamma=gamma0+dgamma*z;
      rb=rb0*sqrt(gamma0./gamma);
      alpha=w*rb./(c*gamma);
      alpha2=alpha.*alpha;
      p=expint(alpha2); y(1:n)=0;
      ind=find(p~=0);
      y(ind)=exp(alpha2(ind)+log(p(ind))-2*log(gamma(ind))); end;
  end
