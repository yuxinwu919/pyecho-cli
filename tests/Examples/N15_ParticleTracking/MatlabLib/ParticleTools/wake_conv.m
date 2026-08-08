function Out=wake_conv(H,w,wd)
% H=(s,ro) is charge distribution
% w - wake function name
% wd - delta function coef.
% Out=(s,W) - wake
    function y=Int1(x)
        y=(1-x)*w(x*cdt);
    end;
    function y=Int2(x)
        y=(1-abs(x))*w((x+i)*cdt);
    end;

    N=length(H(:,1)); cta=-H(N,1); ctb=-H(1,1);
    cdt=(ctb-cta)/(N-1);
    W=zeros(N,1);
    %some smoothing
    nW=min([100,N-1]);
    W(1)=quad(@Int1,0,1);
    W(1)=W(1)+wd/cdt;
    for i=2:nW,
        W(i)=quad(@Int2,-1,1);
    end;
    if N-1>100,
        W(100:N)=w([100:N]*cdt);
    end;
    %%%%%%%%%%
    pH=H(:,2);
    pH=flipud(pH(:,1));
    U(:,1)=cdt*convmode(pH,W,2);
    U=flipud(U(1:N,1));
    Out=zeros(N,2);
    Out(:,1)=H(:,1);Out(:,2)=U;
end

    